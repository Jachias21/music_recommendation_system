"""
evaluate_models.py — Evaluación profunda del sistema de recomendación
=====================================================================
Protocolo: Carta A
  - Split 80/20 por usuario (hold-out)
  - Eval pool: GT items + 500 negativos aleatorios del catálogo
  - NCF busca sobre el catálogo completo, luego filtra al eval pool
  - Métricas: HR@K, NDCG@K, MRR@K, Catalog Coverage, Novelty, Serendipity

Uso:
    python -m src.evaluation.evaluate_models
    python src/evaluation/evaluate_models.py
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
# CATALOG LOADER  (MongoDB primary, CSV fallback)
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
            if "track_id" in df.columns:
                df["id"] = df["track_id"].astype(str)
            else:
                df["id"] = df["id"].astype(str)
            return df

    print("  CSV no encontrado → MongoDB...")
    try:
        from src.data.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME
        from pymongo import MongoClient

        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")

        projection = {
            "_id": 0, "track_id": 1, "name": 1, "artist": 1, "emocion": 1,
            "danceability": 1, "energy": 1, "valence": 1, "tempo": 1,
            "acousticness": 1, "instrumentalness": 1, "liveness": 1, "speechiness": 1,
        }
        docs = list(client[DB_NAME][COLLECTION_NAME].find({}, projection))
        df   = pd.DataFrame(docs)
        if df.empty:
            return df
        if "track_id" in df.columns:
            df["id"] = df["track_id"].astype(str)
        else:
            df["id"] = df["id"].astype(str)
        print(f"  MongoDB: {len(df):,} canciones.")
        return df
    except Exception as e:
        print(f"  MongoDB no disponible: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  EVALUACIÓN NCF — Protocolo Carta A")
    print(f"  HR@{K} | NDCG@{K} | MRR@{K} | Coverage | Novelty | Serendipity")
    print(f"  N_users={N_TEST_USERS} | N_neg={N_NEG} | Seed={SEED_SIZE} | GT={GT_SIZE}")
    print("=" * 65)

    # ── 1. Catalog ────────────────────────────────────────────────────────────
    print("\n[1/5] Cargando catálogo...")
    df = _load_catalog(_BASE_DIR)
    if df.empty:
        print("  ERROR: catálogo no encontrado.")
        return

    # Restrict to encoder-known IDs
    enc_path = os.path.join(_BASE_DIR, "models", "item_encoder.pkl")
    with open(enc_path, "rb") as fh:
        _enc = pickle.load(fh)
    encoder_ids = set(str(x) for x in _enc.classes_)
    df = df[df["id"].isin(encoder_ids)].copy().reset_index(drop=True)

    emo_col   = "emocion" if "emocion" in df.columns else "emotion"
    feat_cols = [f for f in FEATURES if f in df.columns]
    print(f"  Catálogo restringido: {len(df):,} canciones")
    print(f"  Emociones: {df[emo_col].unique().tolist()}")
    print(f"  Features  : {feat_cols}")

    catalog_ids_list = df["id"].tolist()

    # ── 2. Interactions ───────────────────────────────────────────────────────
    print("\n[2/5] Cargando interacciones (80/20 hold-out)...")
    inter_path = os.path.join(_BASE_DIR, "data", "processed", "ncf_interactions.csv")
    if not os.path.exists(inter_path):
        print(f"  ERROR: {inter_path} no encontrado.")
        print("  Ejecuta: python scripts/generate_interactions_from_encoder.py")
        return

    inter_df = pd.read_csv(inter_path)
    pos_df   = inter_df[inter_df["label"] == 1].copy()
    pos_df["item_id"] = pos_df["item_id"].astype(str)
    pos_df   = pos_df[pos_df["item_id"].isin(encoder_ids)]

    item_popularity = pos_df["item_id"].value_counts().to_dict()
    total_pos       = len(pos_df)

    # 80/20 hold-out by user
    valid_users = pos_df["user_id"].value_counts()
    valid_users = valid_users[valid_users >= MIN_HISTORY].index.tolist()
    random.seed(42)
    random.shuffle(valid_users)
    n_test = min(N_TEST_USERS, int(len(valid_users) * 0.20))
    test_users = valid_users[:n_test]
    print(f"  Usuarios válidos: {len(valid_users):,} | Test (20%): {len(test_users)}")

    # ── 3. NCF ────────────────────────────────────────────────────────────────
    print("\n[3/5] Cargando NCF Recommender...")
    try:
        ncf = NCFRecommender()
        print("  NCF listo.")
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    # ── 4. Evaluation loop ────────────────────────────────────────────────────
    print(f"\n[4/5] Evaluando {len(test_users)} usuarios...")
    print(f"  {'N':>5}  {'HR_NCF':>7} {'NDCG_NCF':>9} {'MRR_NCF':>8}  "
          f"{'HR_BASE':>7} {'NDCG_BASE':>10} {'MRR_BASE':>9}")
    print("  " + "─" * 60)

    ncf_hr, ncf_ndcg, ncf_mrr, ncf_nov, ncf_seren = [], [], [], [], []
    bas_hr, bas_ndcg, bas_mrr, bas_nov, bas_seren = [], [], [], [], []
    all_ncf_recs, all_base_recs = [], []
    ncf_fallbacks = 0
    per_user_log  = []

    for i, uid in enumerate(test_users):
        u_history = pos_df[pos_df["user_id"] == uid]["item_id"].tolist()
        random.Random(42 + i).shuffle(u_history)

        seeds        = u_history[:SEED_SIZE]
        ground_truth = u_history[SEED_SIZE : SEED_SIZE + GT_SIZE]
        if not ground_truth:
            continue

        gt_set     = set(ground_truth)
        gt_df      = df[df["id"].isin(gt_set)]
        target_emo = gt_df[emo_col].mode().iloc[0] if not gt_df.empty else "Alegre"

        # Eval pool: GT + N_NEG random negatives
        negatives = [
            x for x in random.sample(catalog_ids_list,
                                     min(N_NEG * 2, len(catalog_ids_list)))
            if x not in gt_set
        ][:N_NEG]
        eval_pool = gt_set | set(negatives)

        # — NCF: full catalog → post-filter to eval pool —
        try:
            raw_recs  = ncf.get_recommendations(seeds, target_emo, df, top_n=K * 30)
            ncf_preds = [str(r["id"]) for r in raw_recs if str(r["id"]) in eval_pool][:K]
            if not ncf_preds:
                ncf_fallbacks += 1
        except Exception:
            ncf_preds = []
            ncf_fallbacks += 1

        # — Baseline: full catalog → post-filter to eval pool —
        try:
            user_vec  = create_user_profile(seeds, df)
            raw_base  = get_contextual_recommendations(
                user_vec, target_emo, df, top_n=K * 30, excluded_ids=seeds
            )
            base_preds = [str(r["id"]) for r in raw_base if str(r["id"]) in eval_pool][:K]
        except Exception:
            base_preds = []

        # — Metrics —
        ncf_hr   .append(hit_rate_at_k(ncf_preds,  ground_truth, K))
        ncf_ndcg .append(ndcg_at_k    (ncf_preds,  ground_truth, K))
        ncf_mrr  .append(mrr           (ncf_preds,  ground_truth, K))
        ncf_nov  .append(novelty_at_k  (ncf_preds,  item_popularity, total_pos, K))
        ncf_seren.append(serendipity_at_k(ncf_preds, seeds, ground_truth, df, feat_cols, K))

        bas_hr   .append(hit_rate_at_k(base_preds, ground_truth, K))
        bas_ndcg .append(ndcg_at_k    (base_preds, ground_truth, K))
        bas_mrr  .append(mrr          (base_preds, ground_truth, K))
        bas_nov  .append(novelty_at_k (base_preds, item_popularity, total_pos, K))
        bas_seren.append(serendipity_at_k(base_preds, seeds, ground_truth, df, feat_cols, K))

        all_ncf_recs .append(ncf_preds)
        all_base_recs.append(base_preds)

        per_user_log.append({
            "user_id"       : int(uid),
            "target_emotion": target_emo,
            "seeds"         : seeds,
            "ground_truth"  : ground_truth,
            "ncf"           : {"recommendations": ncf_preds},
            "base"          : {"recommendations": base_preds},
        })

        if (i + 1) % 40 == 0 or i == 0:
            print(f"  {i+1:>5}  "
                  f"{np.mean(ncf_hr):>7.3f} {np.mean(ncf_ndcg):>9.4f} {np.mean(ncf_mrr):>8.4f}  "
                  f"{np.mean(bas_hr):>7.3f} {np.mean(bas_ndcg):>10.4f} {np.mean(bas_mrr):>9.4f}")

    # ── 5. Output ─────────────────────────────────────────────────────────────
    n = len(ncf_hr)
    ncf_cov  = catalog_coverage(all_ncf_recs,  len(df))
    base_cov = catalog_coverage(all_base_recs, len(df))

    output = {
        "protocol"      : "carta_a_holdout_20pct",
        "k"             : K,
        "n_neg"         : N_NEG,
        "n_users"       : n,
        "ncf_fallbacks" : ncf_fallbacks,
        "summary": {
            "ncf": {
                "hit_rate"   : _agg(ncf_hr),
                "ndcg"       : _agg(ncf_ndcg),
                "mrr"        : _agg(ncf_mrr),
                "novelty"    : _agg(ncf_nov),
                "serendipity": _agg(ncf_seren),
                "coverage"   : float(ncf_cov),
                # legacy keys for dashboard
                "precision"  : float(np.mean(ncf_hr)),
                "recall"     : float(np.mean(ncf_ndcg)),
            },
            "base": {
                "hit_rate"   : _agg(bas_hr),
                "ndcg"       : _agg(bas_ndcg),
                "mrr"        : _agg(bas_mrr),
                "novelty"    : _agg(bas_nov),
                "serendipity": _agg(bas_seren),
                "coverage"   : float(base_cov),
                "precision"  : float(np.mean(bas_hr)),
                "recall"     : float(np.mean(bas_ndcg)),
            },
        },
        "users": per_user_log,
    }

    out_path = os.path.join(_BASE_DIR, "data", "evaluation_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    # ── Pretty print ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  RESULTADOS FINALES")
    print("=" * 65)

    def _row(label, ncf_v, base_v, fmt=".4f"):
        delta = ncf_v - base_v
        sign  = "+" if delta >= 0 else ""
        print(f"  {label:<22} NCF={ncf_v:{fmt}}   Base={base_v:{fmt}}   Δ={sign}{delta:{fmt}}")

    print(f"\n  Protocolo  : Carta A — hold-out 20%, {N_NEG} negativos")
    print(f"  Usuarios   : {n}  |  K={K}  |  Fallbacks NCF: {ncf_fallbacks} ({100*ncf_fallbacks/max(1,n):.1f}%)\n")

    _row(f"Hit Rate @ {K}",      np.mean(ncf_hr),    np.mean(bas_hr))
    _row(f"NDCG @ {K}",         np.mean(ncf_ndcg),  np.mean(bas_ndcg))
    _row(f"MRR @ {K}",          np.mean(ncf_mrr),   np.mean(bas_mrr))
    _row("Catalog Coverage",     ncf_cov,             base_cov)
    _row("Novelty",              np.mean(ncf_nov),   np.mean(bas_nov))
    _row("Serendipity",          np.mean(ncf_seren), np.mean(bas_seren))

    print(f"\n  Guardado en: {out_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()