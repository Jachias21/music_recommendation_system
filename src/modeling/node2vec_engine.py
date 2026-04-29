"""
node2vec-based music recommendation engine.

Uses a stratified sample of MAX_TRAIN songs to build the graph and train
embeddings. First run: ~15-25 min. Subsequent runs: ~2 sec (loads from disk).

Offline pre-build:
    python -m src.modeling.node2vec_engine
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
from sklearn.preprocessing import normalize

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
PROCESSED_DIR   = Path(__file__).resolve().parents[2] / "data" / "processed"
EMBEDDINGS_PATH = PROCESSED_DIR / "node2vec_embeddings.npy"
SONG_IDS_PATH   = PROCESSED_DIR / "node2vec_song_ids.npy"
META_PATH       = PROCESSED_DIR / "node2vec_meta.json"

# ── Graph / walk parameters ────────────────────────────────────────────────
GRAPH_K        = 10
GRAPH_FEATURES = ["danceability", "energy", "valence", "tempo",
                  "acousticness", "instrumentalness"]
KNN_BATCH      = 50_000

# node2vec: p=1 (neutral return), q=0.5 (DFS-biased → community discovery)
N2V_P       = 1.0
N2V_Q       = 0.5
N2V_WALK    = 80
N2V_WALKS   = 10
N2V_DIM     = 128
N2V_WINDOW  = 10
N2V_WORKERS = max(1, (os.cpu_count() or 2) - 1)

# Training cap: stratified sample for tractable walk computation
MAX_TRAIN   = 250_000

# ── Module-level cache ─────────────────────────────────────────────────────
_embeddings: np.ndarray | None = None
_song_ids:   np.ndarray | None = None


# ── Graph construction ─────────────────────────────────────────────────────

def _build_knn_csr(features: np.ndarray) -> csr_matrix:
    """K-NN cosine similarity graph as CSR sparse matrix.

    Normalizes features to unit vectors so that euclidean distance is
    equivalent to cosine distance (ball_tree doesn't support cosine directly).
    cosine_dist = euclidean² / 2  →  cosine_sim = 1 - euclidean² / 2
    """
    n = len(features)
    # L2-normalize so euclidean distance ≡ cosine distance
    features_norm = normalize(features, norm="l2")

    logger.info("Fitting NearestNeighbors (k=%d, cosine≡euclidean on L2-norm) on %d nodes…", GRAPH_K, n)
    nn = NearestNeighbors(
        n_neighbors=GRAPH_K + 1,
        metric="euclidean",
        algorithm="ball_tree",
        n_jobs=N2V_WORKERS,
    )
    nn.fit(features_norm)

    rows, cols, data = [], [], []
    for start in range(0, n, KNN_BATCH):
        batch = features_norm[start : start + KNN_BATCH]
        dists, idxs = nn.kneighbors(batch)
        for local_i, (row_dists, row_idxs) in enumerate(zip(dists, idxs)):
            src = start + local_i
            for dist, dst in zip(row_dists, row_idxs):
                dst = int(dst)
                if dst == src:
                    continue
                # euclidean² / 2 = cosine_distance  →  weight = cosine_similarity
                w = max(0.0, 1.0 - float(dist) ** 2 / 2.0)
                if w > 0:
                    rows.append(src)
                    cols.append(dst)
                    data.append(w)
        logger.info("  KNN batch %d/%d done", min(start + KNN_BATCH, n), n)

    return csr_matrix((data, (rows, cols)), shape=(n, n), dtype=np.float32)


# ── Biased random walks ────────────────────────────────────────────────────

def _walk_from(indptr: np.ndarray, indices: np.ndarray, data: np.ndarray,
               start: int, walk_length: int, inv_p: float, inv_q: float,
               rng: np.random.Generator) -> list[str]:
    """Single biased random walk starting from `start`. Returns node IDs as strings."""
    walk = [start]
    prev = -1
    cur  = start

    for _ in range(walk_length - 1):
        nb = indices[indptr[cur] : indptr[cur + 1]]
        wt = data[indptr[cur] : indptr[cur + 1]].copy()
        if len(nb) == 0:
            break

        if prev >= 0:
            prev_nb = indices[indptr[prev] : indptr[prev + 1]]
            # q-bias: nodes not adjacent to prev get weight × 1/q
            # p-bias: the return node (== prev) gets weight × 1/p
            is_prev   = nb == prev
            is_common = np.isin(nb, prev_nb)
            wt[is_prev]                     *= inv_p
            wt[~is_prev & ~is_common]       *= inv_q

        probs = wt / wt.sum()
        prev  = cur
        cur   = int(rng.choice(nb, p=probs))
        walk.append(cur)

    return [str(n) for n in walk]


def _simulate_walks(adj: csr_matrix, num_walks: int, walk_length: int,
                    p: float, q: float) -> list[list[str]]:
    """Generate all node2vec random walks over the graph."""
    indptr  = adj.indptr
    indices = adj.indices
    data    = adj.data
    n       = adj.shape[0]
    inv_p   = 1.0 / p
    inv_q   = 1.0 / q
    rng     = np.random.default_rng(42)

    walks = []
    nodes = np.arange(n)
    total = num_walks * n
    done  = 0

    for walk_num in range(num_walks):
        rng.shuffle(nodes)
        for start in nodes:
            walks.append(_walk_from(indptr, indices, data, int(start),
                                    walk_length, inv_p, inv_q, rng))
            done += 1
            if done % 10_000 == 0:
                logger.info("  walks %d / %d", done, total)

    return walks


# ── Stratified sample ──────────────────────────────────────────────────────

def _stratified_sample(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Sample up to n rows, preserving emotion distribution."""
    if len(df) <= n:
        return df.copy().reset_index(drop=True)

    emotion_col = "emocion" if "emocion" in df.columns else "emotion"
    if emotion_col not in df.columns:
        return df.sample(n, random_state=42).reset_index(drop=True)

    fracs = df[emotion_col].value_counts(normalize=True)
    parts = []
    for emotion, frac in fracs.items():
        k = max(1, int(round(frac * n)))
        subset = df[df[emotion_col] == emotion]
        parts.append(subset.sample(min(k, len(subset)), random_state=42))

    sampled = pd.concat(parts).sample(frac=1, random_state=42).reset_index(drop=True)
    return sampled.head(n)


# ── Train ──────────────────────────────────────────────────────────────────

def _train(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Full pipeline: sample → KNN → walks → Word2Vec. Returns (embeddings, song_ids)."""
    from gensim.models import Word2Vec  # type: ignore

    sample = _stratified_sample(df, MAX_TRAIN)
    logger.info("Training on %d songs (stratified sample from %d)", len(sample), len(df))

    features = sample[GRAPH_FEATURES].fillna(0.0).astype(np.float32).values
    adj = _build_knn_csr(features)

    logger.info("Simulating node2vec walks (p=%.1f, q=%.1f, walks=%d, length=%d)…",
                N2V_P, N2V_Q, N2V_WALKS, N2V_WALK)
    walks = _simulate_walks(adj, N2V_WALKS, N2V_WALK, N2V_P, N2V_Q)

    logger.info("Training Word2Vec (dim=%d, window=%d, workers=%d)…",
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

    # Map local integer IDs back to track ID strings
    local_ids   = np.array([int(k) for k in model.wv.index_to_key], dtype=np.int64)
    track_ids   = sample["id"].astype(str).values[local_ids]
    embeddings  = model.wv.vectors.astype(np.float32)

    return embeddings, track_ids


# ── Cache helpers ──────────────────────────────────────────────────────────

def cache_valid(n_songs: int) -> bool:
    if not (EMBEDDINGS_PATH.exists() and SONG_IDS_PATH.exists() and META_PATH.exists()):
        return False
    try:
        meta = json.loads(META_PATH.read_text())
        # The number of songs might differ slightly if the dataset changes, but we can accept it if files exist.
        return True
    except Exception:
        return False


def get_or_build_embeddings(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Load cached embeddings or train from scratch."""
    if cache_valid(len(df)):
        logger.info("Loading cached node2vec embeddings…")
        return np.load(EMBEDDINGS_PATH), np.load(SONG_IDS_PATH, allow_pickle=True)

    embeddings, song_ids = _train(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_PATH, embeddings)
    np.save(SONG_IDS_PATH, song_ids)
    META_PATH.write_text(json.dumps({
        "n_songs": len(df),
        "max_train": MAX_TRAIN,
        "features": GRAPH_FEATURES,
        "k": GRAPH_K,
    }))
    logger.info("Embeddings saved to %s", PROCESSED_DIR)
    return embeddings, song_ids


def preload_embeddings(df: pd.DataFrame) -> None:
    """Populate module-level cache. Call once at API startup."""
    global _embeddings, _song_ids
    _embeddings, _song_ids = get_or_build_embeddings(df)


# ── Recommendation ─────────────────────────────────────────────────────────

def get_node2vec_recommendations(
    seed_song_ids: list[str],
    target_emotion: str,
    df: pd.DataFrame,
    embeddings: np.ndarray,
    song_ids: np.ndarray,
    top_n: int = 10,
    settings: dict = None,
) -> list[dict]:
    """
    Average seed embeddings → cosine nearest-neighbors filtered by emotion.
    Returns [{id, name, artist, similarity_score}, …].
    """
    if settings is None:
        settings = {"serendipity": 75, "novelty": 40, "instrumentalness": 20, "diversity": "balanced"}

    id_to_idx = {sid: i for i, sid in enumerate(song_ids)}
    seed_vecs = [embeddings[id_to_idx[sid]] for sid in seed_song_ids if sid in id_to_idx]
    if not seed_vecs:
        logger.warning("No seed songs found in embedding index.")
        return []

    query = np.mean(seed_vecs, axis=0, keepdims=True)

    emotion_col = "emocion" if "emocion" in df.columns else "emotion"
    emotion_ids = set(
        df[df[emotion_col].str.lower() == target_emotion.lower()]["id"].astype(str)
    )
    seed_set = set(seed_song_ids)
    mask = np.array(
        [sid in emotion_ids and sid not in seed_set for sid in song_ids], dtype=bool
    )
    if not mask.any():
        logger.warning("No candidates for emotion '%s'.", target_emotion)
        return []

    candidate_emb = embeddings[mask]
    candidate_ids = song_ids[mask]
    scores = cosine_similarity(query, candidate_emb)[0]

    # --- Apply Settings ---
    serendipity = settings.get("serendipity", 75) / 100.0
    instrumentalness_pref = settings.get("instrumentalness", 20) / 100.0
    diversity = settings.get("diversity", "balanced")

    # Step 1: Sort ALL candidates by raw cosine similarity
    sorted_indices = np.argsort(scores)[::-1]

    # Step 2: Diversity — pick *which* candidates to consider
    n_candidates = len(sorted_indices)
    if diversity == "focused":
        # Only look at the very top 12: safe, coherent but repetitive
        pool_indices = sorted_indices[: min(12, n_candidates)]
    elif diversity == "wide":
        # Spread selection: take some from top, some from mid, some from further out
        top_chunk  = sorted_indices[: min(10, n_candidates)]
        mid_chunk  = sorted_indices[min(10, n_candidates): min(100, n_candidates)]
        far_chunk  = sorted_indices[min(100, n_candidates): min(500, n_candidates)]

        # Proportions: 40% top, 40% mid, 20% far (adjust as needed)
        n_top = max(4, int(top_n * 0.4))
        n_mid = max(4, int(top_n * 0.4))
        n_far = max(2, top_n - n_top - n_mid)

        mid_sample = mid_chunk[: min(n_mid, len(mid_chunk))]
        far_sample = np.random.choice(far_chunk, size=min(n_far, len(far_chunk)), replace=False) if len(far_chunk) > 0 else np.array([], dtype=int)

        pool_indices = np.concatenate([top_chunk[:n_top], mid_sample, far_sample]).astype(int)
    else:  # balanced
        # Top 20: better than focused, not as wild as wide
        pool_indices = sorted_indices[: min(20, n_candidates)]

    # Step 3: Re-rank the pool with serendipity noise + instrumentalness
    pool_scores = scores[pool_indices].copy()
    pool_ids = candidate_ids[pool_indices]

    meta_df = df[df["id"].astype(str).isin(pool_ids)].set_index("id")

    for i, sid in enumerate(pool_ids):
        # Serendipity: random noise proportional to level
        if serendipity > 0:
            noise = (np.random.random() * 0.20) * serendipity
            pool_scores[i] += noise

        # Instrumentalness boost/penalty
        if "instrumentalness" in meta_df.columns and sid in meta_df.index:
            inst_val = float(meta_df.loc[sid, "instrumentalness"] or 0.0)
            if instrumentalness_pref > 0.5 and inst_val > 0.5:
                pool_scores[i] += 0.05
            elif instrumentalness_pref < 0.3 and inst_val > 0.5:
                pool_scores[i] -= 0.05

    # Step 4: Final sort → pick top_n winners
    final_sort = np.argsort(pool_scores)[::-1][:top_n]
    top_ids    = pool_ids[final_sort]
    top_scores = pool_scores[final_sort]
    
    # Ensure meta_df covers all top_ids (it already does from the subset)
    meta_df = df[df["id"].astype(str).isin(top_ids)].set_index("id")[["name", "artist", "track_id"] if "track_id" in df.columns else ["name", "artist"]]

    results = []
    for sid, score_val in zip(top_ids, top_scores):
        row = meta_df.loc[sid] if sid in meta_df.index else None
        
        # Cap the output score visually to 0.99 (99%) so it doesn't break the UI
        display_score = min(float(score_val), 0.99)
        
        results.append({
            "id": sid,
            "track_id": str(row["track_id"]) if (row is not None and "track_id" in row) else sid,
            "name": row["name"] if row is not None else "",
            "artist": row["artist"] if row is not None else "",
            "similarity_score": display_score,
        })
    return results


# ── CLI: offline pre-build ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from src.modeling.recommendation_engine import get_mongodb_data  # type: ignore
    from src.data.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME  # type: ignore

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    df = get_mongodb_data(MONGO_URI, DB_NAME, COLLECTION_NAME)
    if "_id" in df.columns and "id" not in df.columns:
        df["id"] = df["_id"].astype(str)
    elif "id" in df.columns:
        df["id"] = df["id"].astype(str)

    get_or_build_embeddings(df)
    print("Done. Embeddings saved to", PROCESSED_DIR)
