"""
generate_interactions_from_encoder.py
=====================================
Genera el dataset de interacciones sintéticas usando ÚNICAMENTE los IDs
que el item_encoder del NCF conoce (track_id en MongoDB).

Esto garantiza que el evaluador nunca encuentre OOV (Out-of-Vocabulary)
al pasar seeds al NCF.

Uso:
    python scripts/generate_interactions_from_encoder.py

Output:
    data/processed/ncf_interactions.csv   ← sobrescribe el anterior
"""

import os
import sys
import csv
import pickle
import random
import numpy as np
import pandas as pd
from pymongo import MongoClient

# ── Path setup ────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from src.data.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME

# ── Config ────────────────────────────────────────────────────────────────────
NUM_USERS          = 100_000
MIN_POS_INTERACTIONS = 20
MAX_POS_INTERACTIONS = 50
NEGATIVE_RATIO     = 4
CHUNK_SIZE         = 50_000

ENCODER_PATH = os.path.join(_BASE_DIR, "models", "item_encoder.pkl")
OUTPUT_PATH  = os.path.join(_BASE_DIR, "data", "processed", "ncf_interactions.csv")


def main():
    print("=" * 60)
    print("GENERADOR DE INTERACCIONES — Basado en Encoder NCF")
    print(f"  Usuarios sintéticos : {NUM_USERS:,}")
    print(f"  Negative Ratio      : {NEGATIVE_RATIO}")
    print("=" * 60)

    # ── 1. Load encoder known IDs ─────────────────────────────────────────────
    print(f"\n[1/4] Cargando IDs conocidos del encoder: {ENCODER_PATH}")
    with open(ENCODER_PATH, "rb") as f:
        enc = pickle.load(f)
    encoder_ids = set(str(x) for x in enc.classes_)
    print(f"  Encoder conoce {len(encoder_ids):,} IDs de canciones.")

    # ── 2. Load catalog from MongoDB (only encoder-known songs) ───────────────
    print(f"\n[2/4] Cargando catálogo desde MongoDB (solo IDs del encoder)...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    col    = client[DB_NAME][COLLECTION_NAME]

    projection = {"_id": 0, "track_id": 1, "emocion": 1,
                  "danceability": 1, "energy": 1, "valence": 1,
                  "acousticness": 1, "instrumentalness": 1}

    docs = list(col.find(
        {"track_id": {"$in": list(encoder_ids)}},
        projection
    ))
    client.close()

    df = pd.DataFrame(docs)
    df.rename(columns={"track_id": "id"}, inplace=True)
    df["id"] = df["id"].astype(str)
    df = df[df["id"].isin(encoder_ids)].drop_duplicates(subset=["id"])

    print(f"  Canciones recuperadas de MongoDB : {len(df):,}")
    print(f"  Cobertura del encoder            : {100*len(df)/len(encoder_ids):.1f}%")

    if df.empty:
        print("  ERROR: No se encontraron canciones. Verifica MONGO_URI y la colección.")
        return

    emo_col = "emocion" if "emocion" in df.columns else "emotion"
    all_emotions = df[emo_col].dropna().unique().tolist()
    print(f"  Emociones disponibles: {all_emotions}")

    # ── 3. Precompute per-emotion pools with Pareto weights ───────────────────
    print(f"\n[3/4] Construyendo pools por emoción con distribución Pareto...")
    songs_by_emotion  = {}
    weights_by_emotion = {}

    for emo in all_emotions:
        sub = df[df[emo_col] == emo]
        if sub.empty:
            continue
        songs_by_emotion[emo] = sub["id"].values
        # Pareto 80/20: weight by (valence * energy) proxying popularity
        w = (sub["valence"].fillna(0.5) * sub["energy"].fillna(0.5)).values.astype(np.float64) ** 2.0
        w_sum = w.sum()
        weights_by_emotion[emo] = w / w_sum if w_sum > 0 else np.ones(len(w)) / len(w)
        print(f"  {emo:12s}: {len(sub):>8,} canciones")

    if not songs_by_emotion:
        print("  ERROR: No hay emociones disponibles para generar interacciones.")
        return

    # ── 4. Generate interactions ──────────────────────────────────────────────
    print(f"\n[4/4] Generando {NUM_USERS:,} usuarios (chunk={CHUNK_SIZE:,})...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    total_pos = 0
    total_neg = 0
    chunk_buffer = []

    with open(OUTPUT_PATH, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["user_id", "item_id", "label"])

        for user_id in range(1, NUM_USERS + 1):
            fav_emotions = random.sample(all_emotions, k=random.choice([1, 2]))
            num_pos = random.randint(MIN_POS_INTERACTIONS, MAX_POS_INTERACTIONS)

            # Positive interactions
            user_pos_songs = set()
            for emo in fav_emotions:
                pool    = songs_by_emotion[emo]
                weights = weights_by_emotion[emo]
                target_n = max(1, num_pos // len(fav_emotions))
                target_n = min(target_n, len(pool))
                chosen  = np.random.choice(pool, size=target_n, replace=False, p=weights)
                user_pos_songs.update(chosen)

            for song_id in user_pos_songs:
                chunk_buffer.append((user_id, song_id, 1))
            total_pos += len(user_pos_songs)

            # Negative sampling (non-favourite emotions)
            num_neg = len(user_pos_songs) * NEGATIVE_RATIO
            non_fav = [e for e in all_emotions if e not in fav_emotions]
            user_neg_songs = set()
            if non_fav:
                for emo in non_fav:
                    pool    = songs_by_emotion[emo]
                    weights = weights_by_emotion[emo]
                    target_n = max(1, num_neg // len(non_fav))
                    target_n = min(target_n, len(pool))
                    chosen  = np.random.choice(pool, size=target_n, replace=False, p=weights)
                    user_neg_songs.update(chosen)

            for song_id in list(user_neg_songs)[:num_neg]:
                chunk_buffer.append((user_id, song_id, 0))
            total_neg += min(len(user_neg_songs), num_neg)

            # Flush chunk
            if len(chunk_buffer) >= CHUNK_SIZE:
                writer.writerows(chunk_buffer)
                chunk_buffer.clear()

            if user_id % 10_000 == 0:
                print(f"  ... {user_id:,}/{NUM_USERS:,} usuarios procesados")

        if chunk_buffer:
            writer.writerows(chunk_buffer)

    total = total_pos + total_neg
    file_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\nFinalizado.")
    print(f"  Interacciones totales : {total:,}")
    print(f"    → Positivas         : {total_pos:,}")
    print(f"    → Negativas         : {total_neg:,}  (ratio x{NEGATIVE_RATIO})")
    print(f"  Archivo               : {OUTPUT_PATH}")
    print(f"  Tamaño en disco       : {file_mb:.1f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
