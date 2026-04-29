"""
evaluate_models.py — Evaluación profunda del sistema de recomendación
=====================================================================
Protocolo: Carta A (Actualizado para incluir Node2Vec)
  - Split 80/20 por usuario (hold-out)
  - Eval pool: GT items + 500 negativos aleatorios del catálogo
  - Modelos evaluados: NCF, Baseline (Contenido), Node2Vec
  - Métricas: HR@K, NDCG@K, MRR@K, Catalog Coverage, Novelty, Serendipity

Uso:
    python -m src.evaluation.evaluate_models
"""

import os
import sys
import json
import random
import pickle
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings("ignore")

# ── Path setup ────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from src.modeling.ncf_inference import NCFRecommender
from src.modeling.recommendation_engine import (
    get_contextual_recommendations,
    create_user_profile,
    FEATURES,
)
from src.modeling.node2vec_engine import get_node2vec_recommendations, get_or_build_embeddings


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
K            = 10     # rank cutoff
N_NEG        = 500    # random negatives per user in the eval pool
N_TEST_USERS = 200    # users to evaluate
SEED_SIZE    = 5      # interactions used as input
GT_SIZE      = 10     # interactions used as ground truth
MIN_HISTORY  = SEED_SIZE + GT_SIZE


# ─────────────────────────────────────────────────────────────────────────────
# METRIC FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def hit_rate_at_k(recommended: list, ground_truth: list, k: int = 10) -> float:
    return float(len(set(recommended[:k]) & set(ground_truth)) > 0)


def ndcg_at_k(recommended: list, ground_truth: list, k: int = 10) -> float:
    gt_set = set(ground_truth)
    dcg = sum(
        1.0 / np.log2(i + 2)
        for i, item in enumerate(recommended[:k])
        if item in gt_set
    )
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(gt_set))))
    return dcg / idcg if idcg > 0 else 0.0


def mrr(recommended: list, ground_truth: list, k: int = 10) -> float:
    gt_set = set(ground_truth)
    for rank, item in enumerate(recommended[:k], start=1):
        if item in gt_set:
            return 1.0 / rank
    return 0.0


def novelty_at_k(
    recommended: list,
    item_popularity: dict,
    total_interactions: int,
    k: int = 10,
) -> float:
    if not recommended:
        return 0.0
    scores = []
    for item in recommended[:k]:
        freq = item_popularity.get(str(item), 1)
        p = freq / total_interactions
        scores.append(-np.log2(p + 1e-10))
    return float(np.mean(scores))


def serendipity_at_k(
    recommended: list,
    seeds: list,
    ground_truth: list,
    df: pd.DataFrame,
    feature_cols: list,
    k: int = 10,
) -> float:
    if not recommended or not seeds or not feature_cols:
        return 0.0

    id_to_features = df.set_index("id")[feature_cols]

    def get_vec(item_id):
        try:
            return id_to_features.loc[str(item_id)].values.astype(float)
        except KeyError:
            return None

    seed_vecs = [v for s in seeds if (v := get_vec(s)) is not None]
    if not seed_vecs:
        return 0.0

    centroid = np.mean(seed_vecs, axis=0).reshape(1, -1)
    gt_set = set(ground_truth)
    serendipitous = 0

    for item in recommended[:k]:
        if item not in gt_set:
            continue
        item_vec = get_vec(item)
        if item_vec is None:
            continue
        sim = cosine_similarity(centroid, item_vec.reshape(1, -1))[0][0]
        if (1.0 - sim) > 0.5:
            serendipitous += 1

    return serendipitous / min(k, len(recommended))


def catalog_coverage(all_recommendations: list, catalog_size: int) -> float:
    unique = set()
    for rec_list in all_recommendations:
        unique.update(rec_list)
    return len(unique) / catalog_size if catalog_size > 0 else 0.0


def _agg(values: list) -> dict:
    arr = np.array(values, dtype=float)
    return {"mean": float(np.mean(arr)), "std": float(np.std(arr))}


# ─────────────────────────────────────────────────────────────────────────────
# CATALOG LOADER
# ─────────────────────────────────────────────────────────────────────────────

def _load_catalog(base_dir: str) -> pd.DataFrame:
    csv_candidates = [
        os.path.join(base_dir, "dataset_soundwave_CLEAN_V3.csv"),
        os.path.join(base_dir, "data", "source", "dataset_soundwave_CLEAN_V3.csv"),
    ]
    for path in csv_candidates:
        if os.path.exists(path):
            print(f"  CSV: {path}")
            df = pd.read_csv(path)
            df["id"] = df["track_id"].astype(str) if "track_id" in df.columns else df["id"].astype(str)
            return df

    print("  CSV no encontrado → MongoDB...")
    try:
        from src.data.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        projection = {
            "_id": 0, "track_id": 1, "name": 1, "artist": 1, "emocion": 1,
            "danceability": 1, "energy": 1, "valence": 1, "tempo": 1,
            "acousticness": 1, "instrumentalness": 1, "liveness": 1, "speechiness": 1,
        }
        docs = list(client[DB_NAME][COLLECTION_NAME].find({}, projection))
        df = pd.DataFrame(docs)
        if not df.empty:
            df["id"] = df["track_id"].astype(str) if "track_id" in df.columns else df["id"].astype(str)
        print(f"  MongoDB: {len(df):,} canciones.")
        return df
    except Exception as e:
        print(f"  Error MongoDB: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 75)
    print("  EVALUACIÓN COMPARATIVA: NCF vs Node2Vec vs Baseline")
    print(f"  Métricas: HR@{K} | NDCG@{K} | MRR@{K} | Coverage | Novelty | Serendipity")
    print("=" * 75)

    # 1. Catalog
    print("\n[1/5] Cargando catálogo...")
    df = _load_catalog(_BASE_DIR)
    if df.empty: return

    # IDs del encoder (punto común de verdad)
    enc_path = os.path.join(_BASE_DIR, "models", "item_encoder.pkl")
    with open(enc_path, "rb") as fh:
        _enc = pickle.load(fh)
    encoder_ids = set(str(x) for x in _enc.classes_)
    df = df[df["id"].isin(encoder_ids)].copy().reset_index(drop=True)
    catalog_ids_list = df["id"].tolist()
    feat_cols = [f for f in FEATURES if f in df.columns]
    emo_col = "emocion" if "emocion" in df.columns else "emotion"

    # 2. Interactions
    print("\n[2/5] Cargando interacciones (80/20 split)...")
    inter_path = os.path.join(_BASE_DIR, "data", "processed", "ncf_interactions.csv")
    inter_df = pd.read_csv(inter_path)
    pos_df = inter_df[inter_df["label"] == 1].copy()
    pos_df["item_id"] = pos_df["item_id"].astype(str)
    pos_df = pos_df[pos_df["item_id"].isin(encoder_ids)]
    item_popularity = pos_df["item_id"].value_counts().to_dict()
    total_pos = len(pos_df)

    valid_users = pos_df["user_id"].value_counts()
    valid_users = valid_users[valid_users >= MIN_HISTORY].index.tolist()
    random.seed(42)
    random.shuffle(valid_users)
    test_users = valid_users[:min(N_TEST_USERS, int(len(valid_users)*0.2))]
    print(f"  Usuarios de test: {len(test_users)}")

    # 3. Models
    print("\n[3/5] Inicializando modelos...")
    ncf = NCFRecommender()
    n2v_embeddings, n2v_song_ids = get_or_build_embeddings(df)
    print("  Modelos cargados.")

    # 4. Loop
    print(f"\n[4/5] Evaluando {len(test_users)} usuarios...")
    print(f"{'User':>5} | {'NCF_HR':>7} | {'N2V_HR':>7} | {'BAS_HR':>7}")
    print("-" * 45)

    res = {m: defaultdict(list) for m in ["ncf", "n2v", "base"]}
    all_recs = {m: [] for m in ["ncf", "n2v", "base"]}
    per_user_log = []

    for i, uid in enumerate(test_users):
        u_hist = pos_df[pos_df["user_id"] == uid]["item_id"].tolist()
        random.Random(42+i).shuffle(u_hist)
        seeds, gt = u_hist[:SEED_SIZE], u_hist[SEED_SIZE:SEED_SIZE+GT_SIZE]
        if not gt: continue
        
        gt_set = set(gt)
        gt_df = df[df["id"].isin(gt_set)]
        target_emo = gt_df[emo_col].mode().iloc[0] if not gt_df.empty else "Alegre"

        # Eval pool
        negatives = [x for x in random.sample(catalog_ids_list, min(N_NEG*2, len(df))) if x not in gt_set][:N_NEG]
        eval_pool = gt_set | set(negatives)

        # Inferences
        # NCF
        try:
            raw = ncf.get_recommendations(seeds, target_emo, df, top_n=K*30)
            p_ncf = [str(r["id"]) for r in raw if str(r["id"]) in eval_pool][:K]
        except: p_ncf = []
        
        # Node2Vec
        try:
            raw = get_node2vec_recommendations(seeds, target_emo, df, n2v_embeddings, n2v_song_ids, top_n=K*30)
            p_n2v = [str(r["id"]) for r in raw if str(r["id"]) in eval_pool][:K]
        except: p_n2v = []

        # Baseline
        try:
            uv = create_user_profile(seeds, df)
            raw = get_contextual_recommendations(uv, target_emo, df, top_n=K*30, excluded_ids=seeds)
            p_bas = [str(r["id"]) for r in raw if str(r["id"]) in eval_pool][:K]
        except: p_bas = []

        # Metrics computation
        for m, preds in [("ncf", p_ncf), ("n2v", p_n2v), ("base", p_bas)]:
            res[m]["hr"].append(hit_rate_at_k(preds, gt, K))
            res[m]["ndcg"].append(ndcg_at_k(preds, gt, K))
            res[m]["mrr"].append(mrr(preds, gt, K))
            res[m]["nov"].append(novelty_at_k(preds, item_popularity, total_pos, K))
            res[m]["ser"].append(serendipity_at_k(preds, seeds, gt, df, feat_cols, K))
            all_recs[m].append(preds)

        if (i+1) % 40 == 0 or i == 0:
            print(f"{i+1:>5} | {np.mean(res['ncf']['hr']):>7.3f} | {np.mean(res['n2v']['hr']):>7.3f} | {np.mean(res['base']['hr']):>7.3f}")

    # 5. Output
    print("\n" + "=" * 75)
    print(f"{'METRICA':<15} | {'NCF':>10} | {'Node2Vec':>10} | {'Baseline':>10}")
    print("-" * 75)
    
    def print_row(label, key):
        print(f"{label:<15} | {np.mean(res['ncf'][key]):10.4f} | {np.mean(res['n2v'][key]):10.4f} | {np.mean(res['base'][key]):10.4f}")

    print_row("Hit Rate@K", "hr")
    print_row("NDCG@K", "ndcg")
    print_row("MRR@K", "mrr")
    print_row("Novelty", "nov")
    print_row("Serendipity", "ser")
    
    # Coverage
    print(f"{'Coverage':<15} | {catalog_coverage(all_recs['ncf'], len(df)):10.4f} | {catalog_coverage(all_recs['n2v'], len(df)):10.4f} | {catalog_coverage(all_recs['base'], len(df)):10.4f}")
    print("=" * 75)

    # Save to JSON
    final_json = {
        "summary": {
            model: {
                metric: _agg(vals) for metric, vals in res[model].items()
            } for model in ["ncf", "n2v", "base"]
        }
    }
    # Add coverage to JSON
    for model in ["ncf", "n2v", "base"]:
        final_json["summary"][model]["coverage"] = catalog_coverage(all_recs[model], len(df))

    out_path = os.path.join(_BASE_DIR, "data", "evaluation_results.json")
    with open(out_path, "w") as f:
        json.dump(final_json, f, indent=2)
    print(f"\nResultados guardados en {out_path}")

if __name__ == "__main__":
    main()