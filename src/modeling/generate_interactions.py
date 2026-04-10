import os
import random
import pandas as pd
from pymongo import MongoClient

# ─────────────────────────────────────────────────────────────────────────────
# Configuración del dataset de interacciones
# ─────────────────────────────────────────────────────────────────────────────
NUM_SONGS_SAMPLE = 50000
NUM_USERS = 3000
MIN_POS_INTERACTIONS = 20
MAX_POS_INTERACTIONS = 50
NEGATIVE_RATIO = 4

def get_mongo_client():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()
        
    uri = os.environ.get("MONGO_URI")
    db_name = os.environ.get("DB_NAME")
    col_name = os.environ.get("COLLECTION_NAME")
    
    client = MongoClient(uri)
    return client[db_name][col_name]

def main():
    print(f"Extrayendo una muestra de {NUM_SONGS_SAMPLE} canciones de MongoDB...")
    collection = get_mongo_client()
    
    # Extraemos una muestra del catálogo asumiendo track_id o id. 
    # El $sample es eficiente si la base es masiva.
    pipeline = [
        {"$sample": {"size": NUM_SONGS_SAMPLE}}, 
        {"$project": {"_id": 0, "id": { "$ifNull": [ "$id", "$track_id" ] }, "emocion": 1}}
    ]
    cursor = collection.aggregate(pipeline, allowDiskUse=True)
    
    df_songs = pd.DataFrame(list(cursor))
    
    if "emocion" not in df_songs.columns or "id" not in df_songs.columns:
        print("[!] Error: La estructura de documentos en MongoDB no coincide (falta id/track_id o emocion).")
        return
        
    df_songs.dropna(subset=["id", "emocion"], inplace=True)
    all_emotions = df_songs["emocion"].unique().tolist()
    
    print(f"Extraídas {len(df_songs)} canciones válidas repartidas en {len(all_emotions)} emociones.")
    
    # Diccionario rápido para muestrear canciones por emoción
    songs_by_emotion = {emotion: df_songs[df_songs["emocion"] == emotion]["id"].tolist() for emotion in all_emotions}
    
    interactions = []
    print(f"Generando interacciones para {NUM_USERS} usuarios sintéticos...")
    
    for user_id in range(1, NUM_USERS + 1):
        # 1. Cada usuario tiene 1 o 2 emociones favoritas
        fav_emotions = random.sample(all_emotions, k=random.choice([1, 2]))
        
        # 2. Recopilamos las canciones positivas ("Likes")
        user_pos_songs = []
        num_pos = random.randint(MIN_POS_INTERACTIONS, MAX_POS_INTERACTIONS)
        
        pool_pos = []
        for em in fav_emotions:
            pool_pos.extend(songs_by_emotion[em])
            
        if len(pool_pos) < num_pos:
            num_pos = len(pool_pos) # Salvar errores si el pool es pequeñísimo
            
        if num_pos > 0:
            user_pos_songs = random.sample(pool_pos, k=num_pos)
            for song_id in user_pos_songs:
                interactions.append({"user_id": user_id, "item_id": song_id, "label": 1})
                
        # 3. Recopilamos el Negative Sampling ("Dislikes" / No escuchadas)
        num_neg = num_pos * NEGATIVE_RATIO
        pool_neg = []
        non_fav_emotions = [e for e in all_emotions if e not in fav_emotions]
        for em in non_fav_emotions:
            pool_neg.extend(songs_by_emotion[em])
            
        if len(pool_neg) < num_neg:
            num_neg = len(pool_neg)
            
        if num_neg > 0:
            user_neg_songs = random.sample(pool_neg, k=num_neg)
            for song_id in user_neg_songs:
                interactions.append({"user_id": user_id, "item_id": song_id, "label": 0})
                
        if user_id % 500 == 0:
            print(f" ... Perfilados {user_id}/{NUM_USERS} usuarios sintéticos")
            
    df_interactions = pd.DataFrame(interactions)
    pos_count = len(df_interactions[df_interactions['label'] == 1])
    neg_count = len(df_interactions[df_interactions['label'] == 0])
    
    print(f"Interacciones generadas con éxito: {len(df_interactions)} filas.")
    print(f" -> Positivas: {pos_count}")
    print(f" -> Negativas: {neg_count} (Ratio x{NEGATIVE_RATIO})")
    
    # 4. Guardar Output en data/processed
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    output_dir = os.path.join(base_dir, "data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "ncf_interactions.csv")
    
    df_interactions.to_csv(out_path, index=False)
    print(f"Output sintético exportado a: data/processed/ncf_interactions.csv")

if __name__ == "__main__":
    main()
