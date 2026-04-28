import os
import csv
import random
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Configuración del dataset de interacciones (Adaptado a V3 CLEAN)
# ─────────────────────────────────────────────────────────────────────────────
NUM_USERS = 100_000            # 100k usuarios sintéticos
MIN_POS_INTERACTIONS = 20
MAX_POS_INTERACTIONS = 50
NEGATIVE_RATIO = 4
CHUNK_SIZE = 50_000            # Escritura en chunks para no saturar RAM

# NUEVO: Ruta directa a tu CSV procesado y limpio
CLEAN_DATASET_PATH = "dataset_soundwave_CLEAN_V3.csv"

def main():
    print("=" * 60)
    print("GENERADOR DE INTERACCIONES v3 — Adaptado a Dataset Clean")
    print(f"  Usuarios sintéticos: {NUM_USERS:,}")
    print(f"  Negative Ratio: {NEGATIVE_RATIO}")
    print("=" * 60)
    
    print(f"\n[1/5] Cargando catálogo limpio desde {CLEAN_DATASET_PATH}...")
    
    if not os.path.exists(CLEAN_DATASET_PATH):
        print(f"❌ ERROR: No se encuentra el archivo {CLEAN_DATASET_PATH}")
        return

    # Leemos tu CSV de Oro
    df_all = pd.read_csv(CLEAN_DATASET_PATH)
    
    # Renombrar track_id a id para mantener compatibilidad con el resto del script
    if 'track_id' in df_all.columns:
        df_all.rename(columns={'track_id': 'id'}, inplace=True)
        
    df_all.dropna(subset=["id", "emocion", "artist"], inplace=True)
    df_all.drop_duplicates(subset=["id"], inplace=True)
    print(f"  Catálogo validado: {len(df_all):,} canciones puras listas para interactuar.")
    
    # ─────────────────────────────────────────────────────────────────────
    # Distribución de Pareto (80/20) sobre las canciones limpias
    # ─────────────────────────────────────────────────────────────────────
    print("\n[2/5] Construyendo distribución de Pareto (80/20)...")
    artist_counts = df_all['artist'].value_counts()
    
    df_songs = df_all.copy()
    print(f"  Pool final: {len(df_songs):,} canciones de {df_songs['artist'].nunique():,} artistas.")
    
    all_emotions = df_songs["emocion"].dropna().unique().tolist()
    print(f"  Emociones detectadas: {all_emotions}")
    
    # Pesos de popularidad con curva de Pareto agresiva (exponent=2.0)
    artist_weight_dict = artist_counts.to_dict()
    df_songs['popularity_weight'] = df_songs['artist'].map(artist_weight_dict).fillna(1)
    
    # Pre-computar arrays por emoción
    songs_by_emotion = {}
    weights_by_emotion = {}
    
    for emotion in all_emotions:
        sub_df = df_songs[df_songs["emocion"] == emotion]
        songs_by_emotion[emotion] = sub_df["id"].values
        w = sub_df["popularity_weight"].values.astype(np.float64) ** 2.0  # Pareto agresivo
        w_sum = w.sum()
        if w_sum > 0:
            weights_by_emotion[emotion] = w / w_sum
        else:
            weights_by_emotion[emotion] = np.ones(len(w)) / len(w)
    
    # Verificación Pareto
    top_20_pct = int(len(df_songs) * 0.20)
    sorted_weights = np.sort(df_songs['popularity_weight'].values)[::-1]
    top_20_weight = sorted_weights[:top_20_pct].sum()
    total_weight = sorted_weights.sum()
    print(f"  Verificación Pareto: Top 20% de canciones acumula {top_20_weight/total_weight*100:.1f}% del peso total.")
    
    # ─────────────────────────────────────────────────────────────────────
    # Generación por Chunks (escritura incremental a disco)
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n[3/5] Generando interacciones para {NUM_USERS:,} usuarios (escritura chunk={CHUNK_SIZE:,})...")
    
    base_dir = os.path.dirname(os.path.dirname(__file__)) # Sube una carpeta (src/)
    base_dir = os.path.dirname(base_dir) # Sube otra a la raíz del proyecto
    
    output_dir = os.path.join(base_dir, "data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "ncf_interactions.csv")
    
    total_pos = 0
    total_neg = 0
    chunk_buffer = []
    
    with open(out_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["user_id", "item_id", "label"])
        
        for user_id in range(1, NUM_USERS + 1):
            fav_emotions = random.sample(all_emotions, k=random.choice([1, 2]))
            num_pos = random.randint(MIN_POS_INTERACTIONS, MAX_POS_INTERACTIONS)
            
            # Interacciones Positivas
            user_pos_songs = set()
            for em in fav_emotions:
                pool = songs_by_emotion[em]
                weights = weights_by_emotion[em]
                target_n = max(1, num_pos // len(fav_emotions))
                target_n = min(target_n, len(pool))
                
                chosen = np.random.choice(pool, size=target_n, replace=False, p=weights)
                user_pos_songs.update(chosen)
                
            for song_id in user_pos_songs:
                chunk_buffer.append((user_id, song_id, 1))
            total_pos += len(user_pos_songs)
                
            # Negative Sampling
            num_neg = len(user_pos_songs) * NEGATIVE_RATIO
            non_fav_emotions = [e for e in all_emotions if e not in fav_emotions]
            
            user_neg_songs = set()
            if non_fav_emotions:
                for em in non_fav_emotions:
                    pool = songs_by_emotion[em]
                    weights = weights_by_emotion[em]
                    target_n = max(1, num_neg // len(non_fav_emotions))
                    target_n = min(target_n, len(pool))
                    chosen = np.random.choice(pool, size=target_n, replace=False, p=weights)
                    user_neg_songs.update(chosen)
                    
            user_neg_list = list(user_neg_songs)[:num_neg]
            for song_id in user_neg_list:
                chunk_buffer.append((user_id, song_id, 0))
            total_neg += len(user_neg_list)
            
            # Flush chunk to disk periodically
            if len(chunk_buffer) >= CHUNK_SIZE:
                writer.writerows(chunk_buffer)
                chunk_buffer.clear()
                
            if user_id % 10_000 == 0:
                print(f"  ... Perfilados {user_id:,}/{NUM_USERS:,} usuarios | Buffer flushed")
        
        # Flush remaining
        if chunk_buffer:
            writer.writerows(chunk_buffer)
            chunk_buffer.clear()
    
    total = total_pos + total_neg
    print(f"\n[4/5] Interacciones generadas con éxito: {total:,} filas.")
    print(f"  -> Positivas: {total_pos:,}")
    print(f"  -> Negativas: {total_neg:,} (Ratio x{NEGATIVE_RATIO})")
    
    # Verificar tamaño del archivo
    file_size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"\n[5/5] Archivo exportado: {out_path}")
    print(f"  Tamaño en disco: {file_size_mb:.1f} MB")
    print("=" * 60)

if __name__ == "__main__":
    main()