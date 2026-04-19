import os
import pandas as pd
from pymongo import MongoClient
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
from src.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME

# ── Genre → Emotion mapping ──────────────────────────────────
GENRE_EMOTION_MAP = {
    # Energetic
    "edm": "energetic", "dance": "energetic", "electronic": "energetic",
    "house": "energetic", "techno": "energetic", "drum-and-bass": "energetic",
    "dubstep": "energetic", "hardstyle": "energetic", "trance": "energetic",
    "club": "energetic", "party": "energetic", "power-pop": "energetic",
    # Happy
    "pop": "happy", "latin": "happy", "reggaeton": "happy", "salsa": "happy",
    "funk": "happy", "disco": "happy", "ska": "happy", "samba": "happy",
    "afrobeat": "happy", "k-pop": "happy", "j-pop": "happy",
    "indie-pop": "happy", "pop-film": "happy",
    # Sad
    "blues": "sad", "emo": "sad", "gospel": "sad", "grunge": "sad",
    "singer-songwriter": "sad", "soul": "sad",
    # Calm
    "acoustic": "calm", "ambient": "calm", "chill": "calm",
    "classical": "calm", "folk": "calm", "jazz": "calm",
    "new-age": "calm", "piano": "calm", "sleep": "calm",
    "study": "calm", "world-music": "calm", "bossanova": "calm",
    "guitar": "calm", "indie": "calm", "indie-pop": "calm",
    # Aggressive
    "metal": "aggressive", "hard-rock": "aggressive", "punk": "aggressive",
    "punk-rock": "aggressive", "death-metal": "aggressive",
    "black-metal": "aggressive", "heavy-metal": "aggressive",
    "metalcore": "aggressive", "hardcore": "aggressive",
    "industrial": "aggressive",
    # Romantic
    "r-n-b": "romantic", "romance": "romantic",
}

def _map_genre_to_emotion(genre: str) -> str:
    """Map a track_genre to a simplified emotion label."""
    if not isinstance(genre, str):
        return "happy"
    return GENRE_EMOTION_MAP.get(genre.lower().strip(), "happy")


def get_mongodb_data(mongo_uri=None, db_name=None, collection_name=None):
    """
    Se conecta a la base de datos MongoDB local, extrae todos los documentos
    de la colección y los devuelve en un DataFrame de Pandas.
    Si falla la conexión a MongoDB, hace fallback al archivo JSON y luego al CSV.
    """
    uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://admin:admin123@127.0.0.1:27018/music_recommendation_db?authSource=admin")
    db_n = db_name or os.getenv("DB_NAME", "music_recommendation_db")
    col_n = collection_name or os.getenv("COLLECTION_NAME", "songs")
    
    df = pd.DataFrame()
    
    # ── Intento 1: MongoDB ──
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        db = client[db_n]
        collection = db[col_n]
        cursor = collection.find({})
        df = pd.DataFrame(list(cursor))
        print(f"[Engine] Leídas {len(df)} canciones desde MongoDB.")
    except Exception as e:
        print(f"[Engine] MongoDB no disponible ({e}).")
    
    # ── Intento 2: JSON local ──
    if df.empty:
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw", "spotify_raw_data.json")
        try:
            import json
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            print(f"[Engine] Fallback JSON exitoso. Leídas {len(df)} canciones.")
        except Exception as json_err:
            print(f"[Engine] JSON no disponible ({json_err}).")

    # ── Intento 3: CSV dataset ──
    if df.empty:
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "source", "dataset_spotify.csv")
        try:
            df = pd.read_csv(csv_path)
            # Normalizar columnas al formato esperado por la app
            rename_map = {"track_id": "id", "artists": "artist", "track_name": "name"}
            df.rename(columns=rename_map, inplace=True)
            # Generar columna de emoción a partir del género
            if "track_genre" in df.columns and "emocion" not in df.columns:
                df["emocion"] = df["track_genre"].apply(_map_genre_to_emotion)
            # Eliminar columna index si existe
            if "Unnamed: 0" in df.columns:
                df.drop(columns=["Unnamed: 0"], inplace=True)
            print(f"[Engine] Fallback CSV exitoso. Leídas {len(df)} canciones.")
        except Exception as csv_err:
            print(f"[Engine] Error leyendo CSV: {csv_err}")
            
    if df.empty:
        return df
        
    # Limpieza: Asegurar que el tempo es numérico y escalar usando MinMaxScaler
    scaler = MinMaxScaler()
    if "tempo" in df.columns:
        df["tempo"] = pd.to_numeric(df["tempo"], errors="coerce").fillna(0)
        df[["tempo"]] = scaler.fit_transform(df[["tempo"]])
        
    # Asegurarnos de que las demás features clave estén listas
    features = ["danceability", "energy", "valence", "acousticness"]
    for f in features:
        if f in df.columns:
            df[f] = pd.to_numeric(df[f], errors="coerce").fillna(0)
            
    return df

def create_user_profile(user_favorite_song_ids, df):
    """
    Simula el 'Onboarding'. Recibe una lista con 3 IDs de canciones favoritas.
    Busca esas canciones en el DataFrame, extrae sus vectores numéricos y 
    calcula la media aritmética de cada columna (danceability, energy, valence, tempo, acousticness).
    
    Devuelve un único vector matemático de 5 dimensiones que representa el 'Centroide' o 'ADN musical'.
    """
    # Filtrar el DataFrame
    id_col = "id" if "id" in df.columns else "_id"
    user_songs_df = df[df[id_col].isin(user_favorite_song_ids)]
    
    if user_songs_df.empty:
        # Array con 5 ceros por defecto si no se encuentran las canciones
        return [0.0] * 5
        
    features = ["danceability", "energy", "valence", "tempo", "acousticness"]
    
    # Quedarnos sólo con las características que realmente existan en el DataFrame
    present_features = [f for f in features if f in user_songs_df.columns]
    
    # Calcular la media aritmética de cada feature para crear el centroide
    user_profile = user_songs_df[present_features].mean().values.tolist()
    
    return user_profile

def get_contextual_recommendations(user_vector, target_emotion, dataframe_base, top_n=5):
    """
    Función central de recomendación.
    Paso A: Filtra el DataFrame base para quedarse únicamente con las canciones 
            cuya emoción coincida con la target_emotion elegida.
    Paso B: Utiliza cosine_similarity para medir la distancia entre el user_vector 
            y la matriz de canciones filtradas.
    Paso C: Ordena los resultados de mayor a menor similitud.
    
    Devuelve una lista de diccionarios (JSON-like) con el Top N de recomendaciones.
    """
    emotion_col = "emocion" if "emocion" in dataframe_base.columns else "emotion"
    if emotion_col not in dataframe_base.columns:
        return []

    # Paso A: Filtrado duro por contexto (emoción) ignorando mayúsculas/minúsculas
    filtered_df = dataframe_base[dataframe_base[emotion_col].astype(str).str.lower() == target_emotion.lower()].copy()
    
    if filtered_df.empty:
        return []
        
    features = ["danceability", "energy", "valence", "tempo", "acousticness"]
    present_features = [f for f in features if f in filtered_df.columns]
    
    if len(present_features) != len(user_vector):
        raise ValueError("La dimensión del vector de usuario no coincide con las características disponibles en la base de datos.")
        
    # Paso B: Similitud del Coseno
    song_matrix = filtered_df[present_features].values
    
    # La validación de scikit-learn requiere que enviemos la matriz como 2D
    similarities = cosine_similarity([user_vector], song_matrix)
    
    # Asignar los scores calculados a nuestro data frame filtrado
    filtered_df["similarity_score"] = similarities[0]
    
    # Paso C: Ranking de mayor a menor similitud
    ranked_df = filtered_df.sort_values(by="similarity_score", ascending=False)
    
    top_recommendations = ranked_df.head(top_n)
    
    # Preparamos la salida final ajustada al formato JSON que las interfaces prefieren
    result = []
    id_col = "id" if "id" in top_recommendations.columns else "_id"
    for _, row in top_recommendations.iterrows():
        name = row.get("name", "Unknown")
        artist = row.get("artist", "Unknown")
        song_id = str(row.get(id_col, ""))
        score = float(row.get("similarity_score", 0.0))
        
        result.append({
            "id": song_id,
            "track_id": str(row.get("track_id", song_id)),
            "name": name,
            "artist": artist,
            "similarity_score": round(score, 4)
        })
        
    return result

if __name__ == "__main__":
    print("Iniciando prueba del Motor de Recomendación...\n")
    
    # Usando la URI del archivo 02 para probar si hay datos cargados en esta base de datos local
    test_uri = "mongodb://admin:admin123@127.0.0.1:27018/music_recommendation_db?authSource=admin"
    test_db = "music_recommendation_db"
    
    try:
        df_songs = get_mongodb_data(mongo_uri=test_uri, db_name=test_db, collection_name="songs")
        print(f"Datos extraídos para la prueba: {len(df_songs)} canciones.")
        
        if not df_songs.empty:
            id_col = "id" if "id" in df_songs.columns else "_id"
            sample_ids = df_songs[id_col].head(3).tolist()
            
            print(f"\nGenerando perfil de usuario basado en (Cold Start) 3 canciones: {sample_ids}")
            user_centroid = create_user_profile(sample_ids, df_songs)
            
            # Formateo visual
            centroid_str = [round(v, 4) for v in user_centroid]
            print(f"Vector resultante de ADN musical (Centroide): {centroid_str}")
            
            emotion_col = "emocion" if "emocion" in df_songs.columns else "emotion"
            sample_emotion = df_songs[emotion_col].iloc[0] if emotion_col in df_songs.columns else "Energetic"
            
            print(f"\nBuscando el Top 5 para contexto emocional: '{sample_emotion}'...\n")
            recs = get_contextual_recommendations(user_vector=user_centroid, target_emotion=str(sample_emotion), dataframe_base=df_songs)
            
            import json
            print("Top Recomendaciones Finales:")
            print(json.dumps(recs, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error durante la prueba. Asegúrate de que MongoDB se está ejecutando y hay datos ingestados: {e}")
