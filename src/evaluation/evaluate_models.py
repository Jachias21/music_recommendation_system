"""
evaluate_models.py — Evaluación de Ultra-Rendimiento (Memory Optimized)
=====================================================================
Optimizado para modelos de gran escala (1.2M items) en entornos con RAM limitada.
Estrategia: Carga perezosa del catálogo filtrada por Pool de Evaluación.
"""

import os
import sys
import json
import random
import pickle
import warnings
import gc
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings("ignore")

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
K            = 10
N_NEG        = 500
N_TEST_USERS = 200
SEED_SIZE    = 5
GT_SIZE      = 10
MIN_HISTORY  = SEED_SIZE + GT_SIZE


# ─────────────────────────────────────────────────────────────────────────────
# METRIC FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def hit_rate_at_k(recommended, ground_truth, k=10):
    return float(len(set(recommended[:k]) & set(ground_truth)) > 0)

def ndcg_at_k(recommended, ground_truth, k=10):
    gt_set = set(ground_truth)
    dcg = sum(1.0 / np.log2(i + 2) for i, item in enumerate(recommended[:k]) if item in gt_set)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(gt_set))))
    return dcg / idcg if idcg > 0 else 0.0

def mrr(recommended, ground_truth, k=10):
    gt_set = set(ground_truth)
    for rank, item in enumerate(recommended[:k], start=1):
        if item in gt_set: return 1.0 / rank
    return 0.0

def novelty_at_k(recommended, item_popularity, total_pos, k=10):
    if not recommended: return 0.0
    scores = [-np.log2(item_popularity.get(str(item), 1) / total_pos + 1e-10) for item in recommended[:k]]
    return float(np.mean(scores))

def serendipity_at_k(recommended, seeds, ground_truth, df_pool, feature_cols, k=10):
    if not recommended or not seeds or not feature_cols: return 0.0
    # df_pool is our micro-catalog containing only pool items
    id_to_features = df_pool.set_index("id")[feature_cols]
    def get_vec(tid):
        try: return id_to_features.loc[str(tid)].values.astype(float)
        except: return None
    svecs = [v for s in seeds if (v := get_vec(s)) is not None]
    if not svecs: return 0.0
    centroid = np.mean(svecs, axis=0).reshape(1, -1)
    gt_set, ser = set(ground_truth), 0
    for item in recommended[:k]:
        if item not in gt_set: continue
        v = get_vec(item)
        if v is not None and (1.0 - cosine_similarity(centroid, v.reshape(1, -1))[0][0]) > 0.5:
            ser += 1
    return ser / min(k, len(recommended))

def catalog_coverage(all_recs, total_ids_count):
    unique = set()
    for rl in all_recs: unique.update(rl)
    return len(unique) / total_ids_count if total_ids_count > 0 else 0.0

def _agg(vals):
    a = np.array(vals, dtype=float)
    return {"mean": float(np.mean(a)), "std": float(np.std(a))}

# ─────────────────────────────────────────────────────────────────────────────
# OPTIMIZED LOADERS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_items_from_mongo(item_ids):
    from src.data.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME
    from pymongo import MongoClient
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    projection = {
        "_id": 0, "track_id": 1, "name": 1, "artist": 1, "emocion": 1,
        "danceability": 1, "energy": 1, "valence": 1, "tempo": 1,
        "acousticness": 1, "instrumentalness": 1, "liveness": 1, "speechiness": 1,
    }
    id_list = list(set(str(i) for i in item_ids))
    chunk_size = 10000
    docs = []
    print(f"  [DB] Fetching {len(id_list):,} documents from MongoDB...")
    for i in range(0, len(id_list), chunk_size):
        chunk = id_list[i:i + chunk_size]
        docs.extend(list(client[DB_NAME][COLLECTION_NAME].find({"track_id": {"$in": chunk}}, projection)))
    df = pd.DataFrame(docs)
    if not df.empty:
        df["id"] = df["track_id"].astype(str)
    return df

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 75)
    print("  EVALUACIÓN DE ALTO RENDIMIENTO: NCF (RE-ENTRENADO) vs OTHERS")
    print("=" * 75)

    # 1. Interactions & Test Users
    print("\n[1/4] Preparando pool de evaluación...")
    inter_path = os.path.join(_BASE_DIR, "data", "processed", "ncf_interactions.csv")
    inter_df = pd.read_csv(inter_path)
    pos_df = inter_df[inter_df["label"] == 1].copy()
    pos_df["item_id"] = pos_df["item_id"].astype(str)
    item_popularity = pos_df["item_id"].value_counts().to_dict()
    total_pos = len(pos_df)

    valid_users = pos_df["user_id"].value_counts()
    valid_users = valid_users[valid_users >= MIN_HISTORY].index.tolist()
    random.seed(42)
    test_users = random.sample(valid_users, min(N_TEST_USERS, len(valid_users)))
    
    # 2. Collect IDs needed for evaluation pool
    print(f"  Collecting items for {len(test_users)} users...")
    all_needed_ids = set()
    user_eval_data = []
    
    # Get all catalog IDs to sample negatives correctly
    # Instead of loading all metadata, just get all IDs
    from pymongo import MongoClient
    from src.data.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME
    client = MongoClient(MONGO_URI)
    all_catalog_ids = [doc["track_id"] for doc in client[DB_NAME][COLLECTION_NAME].find({}, {"track_id": 1, "_id": 0})]
    total_catalog_size = len(all_catalog_ids)

    for i, uid in enumerate(test_users):
        u_hist = pos_df[pos_df["user_id"] == uid]["item_id"].tolist()
        random.Random(42+i).shuffle(u_hist)
        seeds, gt = u_hist[:SEED_SIZE], u_hist[SEED_SIZE:SEED_SIZE+GT_SIZE]
        
        negatives = random.sample(all_catalog_ids, N_NEG)
        eval_pool = set(gt) | set(negatives)
        
        user_eval_data.append({
            "uid": uid, "seeds": seeds, "gt": gt, "pool": eval_pool
        })
        all_needed_ids.update(seeds)
        all_needed_ids.update(eval_pool)

    # Free memory
    del all_catalog_ids
    gc.collect()

    # 3. Load Micro-Catalog (Metadata only for required items)
    print(f"  Pool size: {len(all_needed_ids):,} unique items.")
    df_pool = fetch_items_from_mongo(all_needed_ids)
    del all_needed_ids
    gc.collect()
    
    feat_cols = [f for f in FEATURES if f in df_pool.columns]
    emo_col = "emocion" if "emocion" in df_pool.columns else "emotion"

    # 4. Models
    print("\n[2/4] Inicializando modelos...")
    # NCF Recommender will extract embeddings from the new .pth
    ncf = NCFRecommender()
    
    # Node2Vec (Solo si existen los archivos pre-entrenados)
    n2v_ready = False
    from src.modeling.node2vec_engine import EMBEDDINGS_PATH as N2V_E, SONG_IDS_PATH as N2V_S
    if os.path.exists(N2V_E) and os.path.exists(N2V_S):
        try:
            n2v_embeddings, n2v_song_ids = get_or_build_embeddings(df_pool)
            n2v_ready = True
            print("  Node2Vec cargado con éxito.")
        except Exception as e:
            print(f"  Error cargando Node2Vec: {e}. Se omitirá.")
    else:
        print("  Node2Vec no encontrado (sin pre-entrenar). Se omitirá para agilizar evaluación.")

    print("  Modelos listos.")

    # 5. Loop
    print(f"\n[3/4] Evaluando {len(test_users)} usuarios...")
    print(f"{'User':>5} | {'NCF_HR':>7} | {'N2V_HR':>7} | {'BAS_HR':>7}")
    print("-" * 45)

    # Definir modelos activos
    active_models = ["ncf", "base"]
    if n2v_ready: active_models.append("n2v")

    res = {m: defaultdict(list) for m in active_models}
    all_recs = {m: [] for m in active_models}
    per_user_log = []

    for i, u_data in enumerate(user_eval_data):
        uid, seeds, gt, eval_pool = u_data["uid"], u_data["seeds"], u_data["gt"], u_data["pool"]
        
        gt_df = df_pool[df_pool["id"].isin(set(gt))]
        target_emo = gt_df[emo_col].mode().iloc[0] if not gt_df.empty else "Alegre"

        # Inferences
        results_map = {}
        
        # NCF
        try:
            raw = ncf.get_recommendations(seeds, target_emo, df_pool, top_n=K*30)
            results_map["ncf"] = [str(r["id"]) for r in raw if str(r["id"]) in eval_pool][:K]
        except: results_map["ncf"] = []
        
        # Node2Vec
        if n2v_ready:
            try:
                raw = get_node2vec_recommendations(seeds, target_emo, df_pool, n2v_embeddings, n2v_song_ids, top_n=K*30)
                results_map["n2v"] = [str(r["id"]) for r in raw if str(r["id"]) in eval_pool][:K]
            except: results_map["n2v"] = []

        # Baseline
        try:
            uv = create_user_profile(seeds, df_pool)
            raw = get_contextual_recommendations(uv, target_emo, df_pool, top_n=K*30, excluded_ids=seeds)
            results_map["base"] = [str(r["id"]) for r in raw if str(r["id"]) in eval_pool][:K]
        except: results_map["base"] = []

        # Metrics
        for m in active_models:
            preds = results_map.get(m, [])
            res[m]["hr"].append(hit_rate_at_k(preds, gt, K))
            res[m]["ndcg"].append(ndcg_at_k(preds, gt, K))
            res[m]["mrr"].append(mrr(preds, gt, K))
            res[m]["nov"].append(novelty_at_k(preds, item_popularity, total_pos, K))
            res[m]["ser"].append(serendipity_at_k(preds, seeds, gt, df_pool, feat_cols, K))
            all_recs[m].append(preds)

        per_user_log.append({
            "user_id": int(uid), "target_emotion": target_emo, "seeds": seeds, "ground_truth": gt,
            "ncf": {"recommendations": results_map.get("ncf", [])},
            "n2v": {"recommendations": results_map.get("n2v", [])},
            "base": {"recommendations": results_map.get("base", [])},
        })

        if (i+1) % 40 == 0 or i == 0:
            n2v_hr = np.mean(res['n2v']['hr']) if n2v_ready else 0.0
            print(f"{i+1:>5} | {np.mean(res['ncf']['hr']):>7.3f} | {n2v_hr:>7.3f} | {np.mean(res['base']['hr']):>7.3f}")

    # 6. Final Results
    print("\n" + "=" * 75)
    print(f"{'METRICA':<15} | {'NCF':>10} | {'Node2Vec':>10} | {'Baseline':>10}")
    print("-" * 75)
    
    # Asegurar que todos los modelos tengan entradas (aunque sean ceros) para evitar KeyErrors
    for m in ["ncf", "n2v", "base"]:
        if m not in res:
            res[m] = {met: [0.0] for met in ["hr", "ndcg", "mrr", "nov", "ser"]}
            all_recs[m] = []

    for met in ["hr", "ndcg", "mrr", "nov", "ser"]:
        label = met.upper() + "@K" if met in ["hr", "ndcg", "mrr"] else met.capitalize()
        ncf_val = np.mean(res["ncf"][met])
        n2v_val = np.mean(res["n2v"][met])
        base_val = np.mean(res["base"][met])
        print(f"{label:<15} | {ncf_val:10.4f} | {n2v_val:10.4f} | {base_val:10.4f}")
    
    ncf_cov = catalog_coverage(all_recs['ncf'], total_catalog_size)
    n2v_cov = catalog_coverage(all_recs['n2v'], total_catalog_size)
    base_cov = catalog_coverage(all_recs['base'], total_catalog_size)
    print(f"{'Coverage':<15} | {ncf_cov:10.4f} | {n2v_cov:10.4f} | {base_cov:10.4f}")
    print("=" * 75)

    final_json = {
        "summary": { 
            m: { met: _agg(res[m][met]) for met in ["hr", "ndcg", "mrr", "nov", "ser"] } 
            for m in ["ncf", "n2v", "base"] 
        },
        "users": per_user_log
    }
    final_json["summary"]["ncf"]["coverage"] = ncf_cov
    final_json["summary"]["n2v"]["coverage"] = n2v_cov
    final_json["summary"]["base"]["coverage"] = base_cov

    out_path = os.path.join(_BASE_DIR, "data", "evaluation_results.json")
    with open(out_path, "w") as f:
        json.dump(final_json, f, indent=2)
    print(f"\nResultados guardados en {out_path}")

if __name__ == "__main__":
    main()