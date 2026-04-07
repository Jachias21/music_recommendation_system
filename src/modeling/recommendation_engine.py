import os
import pandas as pd
from pymongo import MongoClient, DESCENDING
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity

# ── Audio features usadas en el vector de usuario y en la similitud ──────────
FEATURES = [
    "danceability", "energy", "valence", "tempo",
    "acousticness", "instrumentalness", "liveness", "speechiness"
]

# Columna de popularidad (puede variar según el origen del dataset)
_POPULARITY_CANDIDATES = ["popularity", "track_popularity"]

# ── Genre → Emotion mapping ──────────────────────────────────────────────────
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
    "guitar": "calm", "indie": "calm",
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


def _get_mongo_client_and_col(uri: str, db_name: str, collection_name: str):
    """Devuelve (client, collection) o lanza excepción si MongoDB no está disponible."""
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    client.admin.command("ping")
    return client, client[db_name][collection_name]


def _detect_popularity_col(collection) -> str | None:
    """Detecta cuál columna de popularidad existe en la colección."""
    sample = collection.find_one({}, projection={c: 1 for c in _POPULARITY_CANDIDATES})
    if sample:
        for c in _POPULARITY_CANDIDATES:
            if c in sample:
                return c
    return None


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte los campos numéricos a float y escala el tempo."""
    scaler = MinMaxScaler()
    if "tempo" in df.columns:
        df["tempo"] = pd.to_numeric(df["tempo"], errors="coerce").fillna(0)
        df[["tempo"]] = scaler.fit_transform(df[["tempo"]])
    for f in FEATURES:
        if f in df.columns:
            df[f] = pd.to_numeric(df[f], errors="coerce").fillna(0)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Carga masiva (usada en arranque para búsquedas y create_user_profile)
# ─────────────────────────────────────────────────────────────────────────────

def get_mongodb_data(mongo_uri=None, db_name=None, collection_name=None):
    """
    Descarga TODOS los documentos de MongoDB a un DataFrame de Pandas.
    Hace fallback a JSON y luego a CSV si Mongo no está disponible.
    Se usa principalmente en el arranque de la API para soportar búsquedas.
    """
    uri = mongo_uri or os.getenv("MONGO_URI")
    db_n = db_name or os.getenv("DB_NAME")
    col_n = collection_name or os.getenv("COLLECTION_NAME")

    df = pd.DataFrame()

    # ── Intento 1: MongoDB ──
    try:
        client, collection = _get_mongo_client_and_col(uri, db_n, col_n)
        cursor = collection.find({})
        df = pd.DataFrame(list(cursor))
        print(f"[Engine] Leídas {len(df)} canciones desde MongoDB.")
    except Exception as e:
        print(f"[Engine] MongoDB no disponible ({e}).")

    # ── Intento 2: JSON local ──
    if df.empty:
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        json_path = os.path.join(base, "data", "raw", "spotify_raw_data.json")
        try:
            import json
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            print(f"[Engine] Fallback JSON exitoso. Leídas {len(df)} canciones.")
        except Exception as err:
            print(f"[Engine] JSON no disponible ({err}).")

    # ── Intento 3: CSV ──
    if df.empty:
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        csv_path = os.path.join(base, "data", "source", "dataset_spotify.csv")
        try:
            df = pd.read_csv(csv_path)
            df.rename(columns={"track_id": "id", "artists": "artist", "track_name": "name"}, inplace=True)
            if "track_genre" in df.columns and "emocion" not in df.columns:
                df["emocion"] = df["track_genre"].apply(_map_genre_to_emotion)
            if "Unnamed: 0" in df.columns:
                df.drop(columns=["Unnamed: 0"], inplace=True)
            print(f"[Engine] Fallback CSV exitoso. Leídas {len(df)} canciones.")
        except Exception as err:
            print(f"[Engine] Error leyendo CSV: {err}")

    if df.empty:
        return df

    return _normalize_df(df)


# ─────────────────────────────────────────────────────────────────────────────
# Pre-filtrado directo en MongoDB para recomendaciones
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_candidates_from_mongo(uri, db_n, col_n, target_emotion: str, pop_col: str, limit: int = 20_000) -> pd.DataFrame:
    """
    Consulta MongoDB filtrando por emoción y popularidad mínima.
    Devuelve un DataFrame con las `limit` canciones más populares de esa emoción.
    """
    client, collection = _get_mongo_client_and_col(uri, db_n, col_n)
    query = {"emocion": {"$regex": f"^{target_emotion}$", "$options": "i"}, pop_col: {"$gte": 20}}
    projection = {f: 1 for f in FEATURES + ["id", "name", "artist", "emocion", pop_col]}
    projection["_id"] = 0
    cursor = (
        collection.find(query, projection=projection)
        .sort(pop_col, DESCENDING)
        .limit(limit)
    )
    df = pd.DataFrame(list(cursor))
    print(f"[Engine] Pre-filtrado MongoDB: {len(df)} candidatos para emoción '{target_emotion}'.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Perfil de usuario
# ─────────────────────────────────────────────────────────────────────────────

def create_user_profile(user_favorite_song_ids: list, df: pd.DataFrame) -> list:
    """
    Onboarding: recibe IDs de canciones favoritas, calcula el centroide
    del vector de 8 features de audio.
    """
    id_col = "id" if "id" in df.columns else "_id"
    user_songs_df = df[df[id_col].isin(user_favorite_song_ids)]

    if user_songs_df.empty:
        return [0.0] * len(FEATURES)

    present = [f for f in FEATURES if f in user_songs_df.columns]
    return user_songs_df[present].mean().values.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# Recomendación contextual
# ─────────────────────────────────────────────────────────────────────────────

def get_contextual_recommendations(
    user_vector: list,
    target_emotion: str,
    dataframe_base: pd.DataFrame,
    top_n: int = 5,
    excluded_ids: list = None,
    mongo_uri: str = None,
    db_name: str = None,
    collection_name: str = None,
) -> list:
    """
    Recomienda canciones usando un scoring híbrido:
      final_score = (cosine_similarity × 0.6) + (normalized_popularity × 0.4)

    Flujo:
      1. Intenta obtener candidatos directamente de MongoDB (pre-filtrado).
      2. Fallback al dataframe_base si MongoDB no está disponible.
      3. Excluye las canciones semilla (blacklisting).
      4. Calcula similitud del coseno con el vector de usuario.
      5. Normaliza la popularidad y genera el final_score.
      6. Devuelve el Top N ordenado por final_score.
    """
    uri   = mongo_uri        or os.getenv("MONGO_URI")
    db_n  = db_name          or os.getenv("DB_NAME")
    col_n = collection_name  or os.getenv("COLLECTION_NAME")

    filtered_df = pd.DataFrame()

    # ── Paso 1: Pre-filtrado en MongoDB ──
    if uri and db_n and col_n:
        try:
            client, collection = _get_mongo_client_and_col(uri, db_n, col_n)
            pop_col = _detect_popularity_col(collection)
            if pop_col:
                filtered_df = _fetch_candidates_from_mongo(uri, db_n, col_n, target_emotion, pop_col)
                filtered_df = _normalize_df(filtered_df)
        except Exception as e:
            print(f"[Engine] Pre-filtrado MongoDB falló, usando dataframe_base ({e}).")

    # ── Paso 2: Fallback al DataFrame en memoria ──
    if filtered_df.empty:
        emotion_col = "emocion" if "emocion" in dataframe_base.columns else "emotion"
        if emotion_col not in dataframe_base.columns:
            return []
        filtered_df = dataframe_base[
            dataframe_base[emotion_col].astype(str).str.lower() == target_emotion.lower()
        ].copy()

    if filtered_df.empty:
        return []

    # ── Paso 3: Blacklisting ──
    id_col = "id" if "id" in filtered_df.columns else "_id"
    if excluded_ids:
        filtered_df = filtered_df[~filtered_df[id_col].astype(str).isin([str(i) for i in excluded_ids])]

    if filtered_df.empty:
        return []

    # ── Paso 4: Similitud del coseno ──
    present = [f for f in FEATURES if f in filtered_df.columns]
    if not present:
        return []

    # Recortar el vector de usuario a las dimensiones disponibles
    feature_indices = [FEATURES.index(f) for f in present]
    trimmed_vector = [user_vector[i] for i in feature_indices if i < len(user_vector)]

    if len(trimmed_vector) != len(present):
        return []

    song_matrix = filtered_df[present].values
    similarities = cosine_similarity([trimmed_vector], song_matrix)
    filtered_df = filtered_df.copy()
    filtered_df["similarity_score"] = similarities[0]

    # ── Paso 5: Scoring híbrido ──
    pop_col_df = next((c for c in _POPULARITY_CANDIDATES if c in filtered_df.columns), None)
    if pop_col_df:
        scaler = MinMaxScaler()
        pop_values = pd.to_numeric(filtered_df[pop_col_df], errors="coerce").fillna(0).values.reshape(-1, 1)
        filtered_df["norm_popularity"] = scaler.fit_transform(pop_values)
        filtered_df["final_score"] = (
            filtered_df["similarity_score"] * 0.6 +
            filtered_df["norm_popularity"] * 0.4
        )
        sort_col = "final_score"
    else:
        # Sin columna de popularidad, usar solo similitud
        sort_col = "similarity_score"

    # ── Paso 6: Ranking y serialización ──
    ranked_df = filtered_df.sort_values(by=sort_col, ascending=False).head(top_n)

    result = []
    for _, row in ranked_df.iterrows():
        result.append({
            "id":               str(row.get(id_col, "")),
            "name":             row.get("name", "Unknown"),
            "artist":           row.get("artist", "Unknown"),
            "similarity_score": round(float(row.get("similarity_score", 0.0)), 4),
        })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Prueba manual
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("Iniciando prueba del Motor de Recomendación...\n")

    test_uri = os.getenv("MONGO_URI")
    test_db  = os.getenv("DB_NAME")

    try:
        df_songs = get_mongodb_data(mongo_uri=test_uri, db_name=test_db, collection_name="songs")
        print(f"Datos extraídos para la prueba: {len(df_songs)} canciones.")

        if not df_songs.empty:
            id_col = "id" if "id" in df_songs.columns else "_id"
            sample_ids = df_songs[id_col].head(3).tolist()

            print(f"\nGenerando perfil de usuario (Cold Start) con 3 canciones: {sample_ids}")
            user_centroid = create_user_profile(sample_ids, df_songs)
            print(f"Centroide ({len(user_centroid)} dims): {[round(v, 4) for v in user_centroid]}")

            emotion_col   = "emocion" if "emocion" in df_songs.columns else "emotion"
            sample_emotion = df_songs[emotion_col].iloc[0] if emotion_col in df_songs.columns else "happy"

            print(f"\nBuscando Top 5 para emoción: '{sample_emotion}' (excluyendo canciones semilla)...\n")
            recs = get_contextual_recommendations(
                user_vector=user_centroid,
                target_emotion=str(sample_emotion),
                dataframe_base=df_songs,
                excluded_ids=sample_ids,
            )
            print("Top Recomendaciones Finales:")
            print(json.dumps(recs, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}")
