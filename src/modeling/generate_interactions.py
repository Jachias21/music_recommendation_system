import os
import random
import numpy as np
import pandas as pd
from pymongo import MongoClient

# ─────────────────────────────────────────────────────────────────────────────
# Configuración del dataset de interacciones avanzado
# ─────────────────────────────────────────────────────────────────────────────
NUM_SONGS_SAMPLE = 250000
NUM_USERS = 20000
MIN_POS_INTERACTIONS = 20
MAX_POS_INTERACTIONS = 50
NEGATIVE_RATIO = 4

def get_mongo_client():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
        
    uri = os.environ.get("MONGO_URI", "mongodb://admin:admin123@127.0.0.1:27018/")
    db_name = os.environ.get("DB_NAME", "music_recommendation_db")
    col_name = os.environ.get("COLLECTION_NAME", "songs")
    
    client = MongoClient(uri)
    return client[db_name][col_name]

def main():
    print("Descargando catálogo completo de MongoDB para análisis de popularidad...")
    collection = get_mongo_client()
    
    # Extraemos TODO el catálogo sin $sample
    pipeline = [
        {"$project": {"_id": 0, "id": { "$ifNull": [ "$id", "$track_id" ] }, "artist": 1, "emocion": 1}}
    ]
    cursor = collection.aggregate(pipeline)
    df_all = pd.DataFrame(list(cursor))
    
    df_all.dropna(subset=["id", "emocion", "artist"], inplace=True)
    print(f"Catálogo base cargado: {len(df_all)} canciones.")
    
    # 1. Pipeline de Popularidad (Autoridad del Artista)
    artist_counts = df_all['artist'].value_counts()
    
    # Acumular artistas hasta llegar a ~250.000 canciones
    cumulative_songs = 0
    top_artists = set()
    for artist, count in artist_counts.items():
        top_artists.add(artist)
        cumulative_songs += count
        if cumulative_songs >= NUM_SONGS_SAMPLE:
            break
            
    df_songs = df_all[df_all['artist'].isin(top_artists)].copy()
    print(f"Pool de canciones filtrado (Top Artists): {len(df_songs)} canciones seleccionadas de {len(top_artists)} artistas top.")
    
    all_emotions = df_songs["emocion"].unique().tolist()
    
    # 2. Generar probabilidades (Proxy de Zipf) para Hits Virales
    artist_weight_dict = artist_counts[list(top_artists)].to_dict()
    df_songs['popularity_weight'] = df_songs['artist'].map(artist_weight_dict)
    
    # Pre-calculamos arrays por emoción para numpy.random.choice ultrarrápido
    songs_by_emotion = {}
    weights_by_emotion = {}
    
    for emotion in all_emotions:
        sub_df = df_songs[df_songs["emocion"] == emotion]
        songs_by_emotion[emotion] = sub_df["id"].values
        w = sub_df["popularity_weight"].values ** 1.5  # Elevamos a 1.5 para exagerar la curva (Zipf proxy)
        weights_by_emotion[emotion] = w / w.sum() # Normalizamos a 1
        
    interactions = []
    print(f"Generando interacciones para {NUM_USERS} usuarios sintéticos usando distribución ponderada...")
    
    for user_id in range(1, NUM_USERS + 1):
        fav_emotions = random.sample(all_emotions, k=random.choice([1, 2]))
        num_pos = random.randint(MIN_POS_INTERACTIONS, MAX_POS_INTERACTIONS)
        
        # 3. Recopilar interacciones Ponderadas (Hits)
        user_pos_songs = set()
        for em in fav_emotions:
            pool = songs_by_emotion[em]
            weights = weights_by_emotion[em]
            target_n = max(1, num_pos // len(fav_emotions))
            target_n = min(target_n, len(pool))
            
            chosen = np.random.choice(pool, size=target_n, replace=False, p=weights)
            user_pos_songs.update(chosen)
            
        for song_id in user_pos_songs:
            interactions.append({"user_id": user_id, "item_id": song_id, "label": 1})
            
        # 4. Negative Sampling fuera de sus gustos
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
            interactions.append({"user_id": user_id, "item_id": song_id, "label": 0})
            
        if user_id % 2000 == 0:
            print(f" ... Perfilados {user_id}/{NUM_USERS} usuarios")
            
    df_interactions = pd.DataFrame(interactions)
    pos_count = len(df_interactions[df_interactions['label'] == 1])
    neg_count = len(df_interactions[df_interactions['label'] == 0])
    
    print(f"Interacciones generadas con éxito: {len(df_interactions)} filas.")
    print(f" -> Positivas: {pos_count}")
    print(f" -> Negativas: {neg_count} (Ratio x{NEGATIVE_RATIO})")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    output_dir = os.path.join(base_dir, "data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "ncf_interactions.csv")
    
    df_interactions.to_csv(out_path, index=False)
    print(f"Output sintético de popularidad exportado a: data/processed/ncf_interactions.csv")

if __name__ == "__main__":
    main()
