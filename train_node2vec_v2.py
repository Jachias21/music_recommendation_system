"""
Entrena node2vec con los nuevos datos (dataset_soundwave_COMPLETO.csv) e incluye
'language' como feature adicional. Guarda los artefactos en data/processed_v2.

Uso:
    python train_node2vec_v2.py
"""
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import LabelEncoder, normalize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent
DATA_CSV      = BASE_DIR / "data/source/new_data/dataset_soundwave_COMPLETO.csv"
PROCESSED_DIR = BASE_DIR / "data/processed_v2"

GRAPH_FEATURES = [
    "danceability", "energy", "valence", "tempo",
    "acousticness", "instrumentalness",
    "language_encoded",   # nueva feature
]

GRAPH_K    = 10
KNN_BATCH  = 50_000
N2V_P      = 1.0
N2V_Q      = 0.5
N2V_WALK   = 80
N2V_WALKS  = 10
N2V_DIM    = 128
N2V_WINDOW = 10
N2V_WORKERS = max(1, (os.cpu_count() or 2) - 1)
MAX_TRAIN  = 250_000


# ── Carga y preprocesado ───────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    logger.info("Cargando %s …", DATA_CSV)
    df = pd.read_csv(DATA_CSV, low_memory=False)

    # Normalizar columna de ID
    df = df.rename(columns={"track_id": "id"})

    # Descartar filas sin id ni features clave
    df = df.dropna(subset=["id"] + [c for c in GRAPH_FEATURES if c != "language_encoded"])

    # Codificar idioma como entero (en=0, es=1, …)
    df["language"] = df["language"].fillna("unknown").astype(str).str.lower().str.strip()
    le = LabelEncoder()
    df["language_encoded"] = le.fit_transform(df["language"]).astype(np.float32)

    # Normalizar language_encoded al rango [0, 1] para no dominar sobre el resto
    max_lang = df["language_encoded"].max()
    if max_lang > 0:
        df["language_encoded"] = df["language_encoded"] / max_lang

    logger.info("Dataset cargado: %d canciones, idiomas: %s", len(df), list(le.classes_))
    return df, le


# ── Muestra estratificada ──────────────────────────────────────────────────

def stratified_sample(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if len(df) <= n:
        return df.copy().reset_index(drop=True)

    fracs = df["emocion"].value_counts(normalize=True)
    parts = []
    for emotion, frac in fracs.items():
        k = max(1, int(round(frac * n)))
        subset = df[df["emocion"] == emotion]
        parts.append(subset.sample(min(k, len(subset)), random_state=42))

    return pd.concat(parts).sample(frac=1, random_state=42).reset_index(drop=True).head(n)


# ── KNN graph ─────────────────────────────────────────────────────────────

def build_knn_csr(features: np.ndarray) -> csr_matrix:
    n = len(features)
    features_norm = normalize(features, norm="l2")
    logger.info("NearestNeighbors (k=%d) sobre %d nodos…", GRAPH_K, n)
    nn = NearestNeighbors(n_neighbors=GRAPH_K + 1, metric="euclidean",
                          algorithm="ball_tree", n_jobs=N2V_WORKERS)
    nn.fit(features_norm)

    rows, cols, data = [], [], []
    for start in range(0, n, KNN_BATCH):
        batch = features_norm[start: start + KNN_BATCH]
        dists, idxs = nn.kneighbors(batch)
        for local_i, (row_dists, row_idxs) in enumerate(zip(dists, idxs)):
            src = start + local_i
            for dist, dst in zip(row_dists, row_idxs):
                dst = int(dst)
                if dst == src:
                    continue
                w = max(0.0, 1.0 - float(dist) ** 2 / 2.0)
                if w > 0:
                    rows.append(src)
                    cols.append(dst)
                    data.append(w)
        logger.info("  KNN batch %d/%d hecho", min(start + KNN_BATCH, n), n)

    return csr_matrix((data, (rows, cols)), shape=(n, n), dtype=np.float32)


# ── Random walks ───────────────────────────────────────────────────────────

def walk_from(indptr, indices, data, start, walk_length, inv_p, inv_q, rng):
    walk = [start]
    prev, cur = -1, start
    for _ in range(walk_length - 1):
        nb = indices[indptr[cur]: indptr[cur + 1]]
        wt = data[indptr[cur]: indptr[cur + 1]].copy()
        if len(nb) == 0:
            break
        if prev >= 0:
            prev_nb = indices[indptr[prev]: indptr[prev + 1]]
            is_prev   = nb == prev
            is_common = np.isin(nb, prev_nb)
            wt[is_prev]               *= inv_p
            wt[~is_prev & ~is_common] *= inv_q
        probs = wt / wt.sum()
        prev = cur
        cur  = int(rng.choice(nb, p=probs))
        walk.append(cur)
    return [str(x) for x in walk]


def simulate_walks(adj: csr_matrix) -> list:
    indptr, indices, data = adj.indptr, adj.indices, adj.data
    n     = adj.shape[0]
    inv_p = 1.0 / N2V_P
    inv_q = 1.0 / N2V_Q
    rng   = np.random.default_rng(42)

    walks = []
    nodes = np.arange(n)
    total = N2V_WALKS * n
    done  = 0

    for _ in range(N2V_WALKS):
        rng.shuffle(nodes)
        for start in nodes:
            walks.append(walk_from(indptr, indices, data, int(start),
                                   N2V_WALK, inv_p, inv_q, rng))
            done += 1
            if done % 10_000 == 0:
                logger.info("  walks %d / %d", done, total)
    return walks


# ── Entrenamiento ──────────────────────────────────────────────────────────

def train(df: pd.DataFrame):
    from gensim.models import Word2Vec

    sample = stratified_sample(df, MAX_TRAIN)
    logger.info("Entrenando con %d canciones (muestra de %d)", len(sample), len(df))

    features = sample[GRAPH_FEATURES].fillna(0.0).astype(np.float32).values
    adj      = build_knn_csr(features)

    logger.info("Simulando walks (p=%.1f, q=%.1f, walks=%d, longitud=%d)…",
                N2V_P, N2V_Q, N2V_WALKS, N2V_WALK)
    walks = simulate_walks(adj)

    logger.info("Entrenando Word2Vec (dim=%d, window=%d, workers=%d)…",
                N2V_DIM, N2V_WINDOW, N2V_WORKERS)
    model = Word2Vec(
        sentences=walks,
        vector_size=N2V_DIM,
        window=N2V_WINDOW,
        min_count=0,
        sg=1,
        workers=N2V_WORKERS,
        epochs=10,
        seed=42,
    )

    local_ids  = np.array([int(k) for k in model.wv.index_to_key], dtype=np.int64)
    track_ids  = sample["id"].astype(str).values[local_ids]
    embeddings = model.wv.vectors.astype(np.float32)
    return embeddings, track_ids


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df, lang_encoder = load_data()

    embeddings, song_ids = train(df)

    emb_path  = PROCESSED_DIR / "node2vec_embeddings.npy"
    ids_path  = PROCESSED_DIR / "node2vec_song_ids.npy"
    meta_path = PROCESSED_DIR / "node2vec_meta.json"

    np.save(emb_path, embeddings)
    np.save(ids_path, song_ids)
    meta_path.write_text(json.dumps({
        "n_songs":   len(df),
        "max_train": MAX_TRAIN,
        "features":  GRAPH_FEATURES,
        "k":         GRAPH_K,
        "languages": list(lang_encoder.classes_),
        "source_csv": str(DATA_CSV),
    }, indent=2))

    logger.info("Listo. Artefactos guardados en %s", PROCESSED_DIR)
    logger.info("  embeddings: %s", embeddings.shape)
    logger.info("  song_ids:   %d", len(song_ids))


if __name__ == "__main__":
    main()
