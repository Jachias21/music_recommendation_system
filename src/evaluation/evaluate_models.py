import os
import sys
import pandas as pd
import numpy as np
import random
import time
import json
from pathlib import Path

# Setup paths
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from pymongo import MongoClient
from sklearn.metrics.pairwise import cosine_similarity
from src.modeling.ncf_inference import NCFRecommender
from src.modeling.recommendation_engine import get_contextual_recommendations, create_user_profile, FEATURES

# ==========================================
# METRICS FUNCTIONS
# ==========================================
def precision_at_k(recommended, ground_truth, k=5):
    if len(recommended) == 0: return 0.0
    rec_k = recommended[:k]
    hits = len(set(rec_k).intersection(set(ground_truth)))
    return hits / k

def recall_at_k(recommended, ground_truth, k=5):
    if len(ground_truth) == 0: return 0.0
    rec_k = recommended[:k]
    hits = len(set(rec_k).intersection(set(ground_truth)))
    return hits / len(ground_truth)

def ndcg_at_k(recommended, ground_truth, k=5):
    if len(recommended) == 0: return 0.0
    rec_k = recommended[:k]
    dcg = 0.0
    for i, item in enumerate(rec_k):
        if item in ground_truth:
            dcg += 1.0 / np.log2(i + 2) # i=0 -> log2(2)=1
    
    # IDCG (Ideal DCG)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(ground_truth))))
    
    if idcg == 0: return 0.0
    return dcg / idcg

def calculate_novelty(recommended, item_frequencies, total_interactions, k=5):
    if len(recommended) == 0: return 0.0
    rec_k = recommended[:k]
    nov = 0.0
    for item in rec_k:
        freq = item_frequencies.get(item, 1) # default 1 if not found
        # Inverse Frequency
        p_i = freq / total_interactions
        nov += -np.log2(p_i)
    return nov / k

# ==========================================
# MAIN ROUTINE
# ==========================================
def main():
    print("[EVAL] Carga de variables de entorno...")
    env_path = os.path.join(_BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    print("[EVAL] Conectando a MongoDB para descargar el catálogo (Candidate DF)...")
    uri = os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017")
    db_name = os.environ.get("DB_NAME", "music_recommendation_db")
    col_name = os.environ.get("COLLECTION_NAME", "songs")

    client = MongoClient(uri)
    _df = pd.DataFrame(list(client[db_name][col_name].find({})))

    if "track_id" in _df.columns and "id" not in _df.columns:
        _df["id"] = _df["track_id"].astype(str)
    elif "_id" in _df.columns and "id" not in _df.columns:
        _df["id"] = _df["_id"].astype(str)
    else:
        _df["id"] = _df["id"].astype(str)
        
    print(f"[EVAL] Catálogo cargado: {len(_df)} canciones.")

    print("[EVAL] Cargando interacciones sintéticas de NCF...")
    interactions_path = os.path.join(_BASE_DIR, "data", "processed", "ncf_interactions.csv")
    if not os.path.exists(interactions_path):
        print(f"Error: {interactions_path} no encontrado.")
        return
    
    inter_df = pd.read_csv(interactions_path)
    # Consider only positive interactions (label == 1)
    pos_df = inter_df[inter_df["label"] == 1].copy()
    pos_df["item_id"] = pos_df["item_id"].astype(str)

    # Item Frequencies for Novelty
    item_freq = pos_df["item_id"].value_counts().to_dict()
    total_pos = len(pos_df)

    # Sample 200 Users
    # Filter users with at least 10 positive interactions to have a good split
    user_counts = pos_df["user_id"].value_counts()
    valid_users = user_counts[user_counts >= 10].index.tolist()
    
    if len(valid_users) < 200:
        print("[EVAL] No hay suficientes usuarios validos. Usando todos.")
        test_users = valid_users
    else:
        random.seed(42)
        test_users = random.sample(valid_users, 200)

    print(f"[EVAL] Seleccionados {len(test_users)} usuarios de Test.")

    print("[EVAL] Cargando NCF Recommender...")
    ncf = NCFRecommender()

    # OPTIMIZATION: Cache DataFrames by emotion to avoid 200x full scans
    print("[EVAL] Optimizando catálogo (pre-filtrado por emoción)...")
    emotion_cache = {}
    emo_col = "emocion" if "emocion" in _df.columns else "emotion"
    for emo in _df[emo_col].unique():
        if pd.isna(emo): continue
        emotion_cache[emo.lower()] = _df[_df[emo_col].str.lower() == emo.lower()].copy()

    results = []
    base_metrics = {"precision": [], "recall": [], "ndcg": [], "novelty": []}
    ncf_metrics  = {"precision": [], "recall": [], "ndcg": [], "novelty": []}
    ncf_fallbacks = 0

    print("[EVAL] Iniciando auditoria por usuario...")
    
    for i, u in enumerate(test_users):
        u_history = pos_df[pos_df["user_id"] == u]["item_id"].tolist()
        random.Random(42 + i).shuffle(u_history)
        
        seeds = u_history[:5]
        ground_truth = u_history[5:15]
        
        if not ground_truth:
            continue

        # Determine target emotion from GT
        gt_df = _df[_df["id"].isin(ground_truth)]
        if not gt_df.empty:
            target_emo = gt_df[emo_col].iloc[0]
        else:
            target_emo = "Alegre"
            
        target_emo_key = target_emo.lower()
        candidates = emotion_cache.get(target_emo_key, _df.head(1000))

        # Inferencia NCF
        try:
            ncf_recs = ncf.get_recommendations(
                user_liked_song_ids=seeds,
                target_emotion=target_emo,
                candidate_df=candidates, # Pass matched candidates directly
                top_n=5
            )
            if not ncf_recs:
                ncf_fallbacks += 1
                ncf_preds = []
            else:
                ncf_preds = [r["id"] for r in ncf_recs]
        except Exception as e:
            ncf_preds = []

        # Inferencia Base
        try:
            user_vect = create_user_profile(seeds, _df)
            base_recs = get_contextual_recommendations(
                user_vector=user_vect,
                target_emotion=target_emo,
                dataframe_base=candidates, # Pass matched candidates directly
                top_n=5,
                excluded_ids=seeds
            )
            base_preds = [r["id"] for r in base_recs]
        except Exception as e:
            base_preds = []

        # Metrics
        p_ncf = precision_at_k(ncf_preds, ground_truth, k=5)
        r_ncf = recall_at_k(ncf_preds, ground_truth, k=5)
        ndcg_ncf = ndcg_at_k(ncf_preds, ground_truth, k=5)
        nov_ncf = calculate_novelty(ncf_preds, item_freq, total_pos, k=5)
        
        ncf_metrics["precision"].append(p_ncf)
        ncf_metrics["recall"].append(r_ncf)
        ncf_metrics["ndcg"].append(ndcg_ncf)
        ncf_metrics["novelty"].append(nov_ncf)

        p_base = precision_at_k(base_preds, ground_truth, k=5)
        r_base = recall_at_k(base_preds, ground_truth, k=5)
        ndcg_base = ndcg_at_k(base_preds, ground_truth, k=5)
        nov_base = calculate_novelty(base_preds, item_freq, total_pos, k=5)

        base_metrics["precision"].append(p_base)
        base_metrics["recall"].append(r_base)
        base_metrics["ndcg"].append(ndcg_base)
        base_metrics["novelty"].append(nov_base)

        results.append({
            "user_id": int(u),
            "target_emotion": target_emo,
            "seeds": seeds,
            "ground_truth": ground_truth,
            "ncf": {"recommendations": ncf_preds, "precision": p_ncf, "recall": r_ncf, "ndcg": ndcg_ncf, "novelty": nov_ncf},
            "base": {"recommendations": base_preds, "precision": p_base, "recall": r_base, "ndcg": ndcg_base, "novelty": nov_base}
        })
        
        if (i+1) % 20 == 0:
            print(f"[EVAL] Procesados {i+1}/200 usuarios...")

    print("[EVAL] Consolidando resultados...")
    output = {
        "summary": {
            "ncf": {
                "precision": np.mean(ncf_metrics["precision"]),
                "recall": np.mean(ncf_metrics["recall"]),
                "ndcg": np.mean(ncf_metrics["ndcg"]),
                "novelty": np.mean(ncf_metrics["novelty"]),
                "fallbacks": ncf_fallbacks
            },
            "base": {
                "precision": np.mean(base_metrics["precision"]),
                "recall": np.mean(base_metrics["recall"]),
                "ndcg": np.mean(base_metrics["ndcg"]),
                "novelty": np.mean(base_metrics["novelty"])
            }
        },
        "users": results
    }

    out_path = os.path.join(_BASE_DIR, "data", "evaluation_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"[EVAL] Evaluación completa. Resultados guardados en {out_path}")
    print(json.dumps(output["summary"], indent=4))

if __name__ == "__main__":
    main()
