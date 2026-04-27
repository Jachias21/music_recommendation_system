import os
import sys
import pandas as pd
import numpy as np
import random
import json

# Setup paths
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

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
            dcg += 1.0 / np.log2(i + 2)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(ground_truth))))
    if idcg == 0: return 0.0
    return dcg / idcg

def calculate_novelty(recommended, item_frequencies, total_interactions, k=5):
    if len(recommended) == 0: return 0.0
    rec_k = recommended[:k]
    nov = 0.0
    for item in rec_k:
        freq = item_frequencies.get(item, 1)
        p_i = freq / total_interactions
        nov += -np.log2(p_i)
    return nov / k

# ==========================================
# MAIN ROUTINE
# ==========================================
def main():
    print("=" * 60)
    print("EVALUACIÓN DEL MODELO HÍBRIDO NCF vs BASELINE")
    print("=" * 60)

    print("[EVAL] Cargando el catálogo limpio (Dataset V3 CLEAN)...")
    catalog_path = os.path.join(_BASE_DIR, "dataset_soundwave_CLEAN_V3.csv")
    if not os.path.exists(catalog_path):
        print(f"❌ Error: {catalog_path} no encontrado.")
        return
    
    _df = pd.read_csv(catalog_path)

    # Asegurar que la columna ID sea texto para FAISS
    if "track_id" in _df.columns and "id" not in _df.columns:
        _df["id"] = _df["track_id"].astype(str)
    else:
        _df["id"] = _df["id"].astype(str)
        
    print(f"  Catálogo cargado: {len(_df):,} canciones.")

    print("\n[EVAL] Cargando interacciones sintéticas de NCF...")
    interactions_path = os.path.join(_BASE_DIR, "data", "processed", "ncf_interactions.csv")
    if not os.path.exists(interactions_path):
        print(f"❌ Error: {interactions_path} no encontrado.")
        return
    
    inter_df = pd.read_csv(interactions_path)
    pos_df = inter_df[inter_df["label"] == 1].copy()
    pos_df["item_id"] = pos_df["item_id"].astype(str)

    item_freq = pos_df["item_id"].value_counts().to_dict()
    total_pos = len(pos_df)

    user_counts = pos_df["user_id"].value_counts()
    valid_users = user_counts[user_counts >= 10].index.tolist()
    
    if len(valid_users) < 200:
        test_users = valid_users
    else:
        random.seed(42)
        test_users = random.sample(valid_users, 200)

    print(f"  Seleccionados {len(test_users)} usuarios de Test.")

    print("\n[EVAL] Levantando NCF Recommender (ONNX + FAISS)...")
    ncf = NCFRecommender()

    print("[EVAL] Optimizando caché por emoción...")
    emotion_cache = {}
    emo_col = "emocion" if "emocion" in _df.columns else "emotion"
    for emo in _df[emo_col].unique():
        if pd.isna(emo): continue
        emotion_cache[emo.lower()] = _df[_df[emo_col].str.lower() == emo.lower()].copy()

    results = []
    base_metrics = {"precision": [], "recall": [], "ndcg": [], "novelty": []}
    ncf_metrics  = {"precision": [], "recall": [], "ndcg": [], "novelty": []}
    ncf_fallbacks = 0

    print("\n[EVAL] Iniciando simulaciones de recomendación por usuario...")
    
    for i, u in enumerate(test_users):
        u_history = pos_df[pos_df["user_id"] == u]["item_id"].tolist()
        random.Random(42 + i).shuffle(u_history)
        
        seeds = u_history[:5]
        ground_truth = u_history[5:15]
        if not ground_truth:
            continue

        gt_df = _df[_df["id"].isin(ground_truth)]
        target_emo = gt_df[emo_col].iloc[0] if not gt_df.empty else "Alegre"
        target_emo_key = target_emo.lower()
        candidates = emotion_cache.get(target_emo_key, _df.head(1000))

        # 1. NCF Inference
        try:
            ncf_recs = ncf.get_recommendations(seeds, target_emo, candidates, top_n=5)
            if not ncf_recs:
                ncf_fallbacks += 1
                ncf_preds = []
            else:
                ncf_preds = [r["id"] for r in ncf_recs]
        except Exception:
            ncf_preds = []

        # 2. Base Inference (Acoustic Match)
        try:
            user_vect = create_user_profile(seeds, _df)
            base_recs = get_contextual_recommendations(user_vect, target_emo, candidates, top_n=5, excluded_ids=seeds)
            base_preds = [r["id"] for r in base_recs]
        except Exception:
            base_preds = []

        # Metrics NCF
        p_ncf = precision_at_k(ncf_preds, ground_truth, k=5)
        r_ncf = recall_at_k(ncf_preds, ground_truth, k=5)
        ndcg_ncf = ndcg_at_k(ncf_preds, ground_truth, k=5)
        nov_ncf = calculate_novelty(ncf_preds, item_freq, total_pos, k=5)
        
        ncf_metrics["precision"].append(p_ncf)
        ncf_metrics["recall"].append(r_ncf)
        ncf_metrics["ndcg"].append(ndcg_ncf)
        ncf_metrics["novelty"].append(nov_ncf)

        # Metrics Base
        p_base = precision_at_k(base_preds, ground_truth, k=5)
        r_base = recall_at_k(base_preds, ground_truth, k=5)
        ndcg_base = ndcg_at_k(base_preds, ground_truth, k=5)
        nov_base = calculate_novelty(base_preds, item_freq, total_pos, k=5)

        base_metrics["precision"].append(p_base)
        base_metrics["recall"].append(r_base)
        base_metrics["ndcg"].append(ndcg_base)
        base_metrics["novelty"].append(nov_base)

        if (i+1) % 20 == 0:
            print(f"  ... Auditados {i+1}/200 usuarios")

    print("\n[EVAL] Consolidando resultados...")
    output = {
        "summary": {
            "ncf": {
                "precision": float(np.mean(ncf_metrics["precision"])),
                "ndcg": float(np.mean(ncf_metrics["ndcg"])),
                "novelty": float(np.mean(ncf_metrics["novelty"]))
            },
            "baseline": {
                "precision": float(np.mean(base_metrics["precision"])),
                "ndcg": float(np.mean(base_metrics["ndcg"])),
                "novelty": float(np.mean(base_metrics["novelty"]))
            }
        }
    }

    out_path = os.path.join(_BASE_DIR, "data", "evaluation_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"\n✅ Evaluación completa. Resultados guardados en {out_path}")
    print("\n🏆 RESULTADOS FINALES:")
    print(json.dumps(output["summary"], indent=4))

if __name__ == "__main__":
    main()