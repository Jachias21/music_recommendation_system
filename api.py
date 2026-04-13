"""
FastAPI REST layer — wraps existing backend functions for the Angular frontend.
Does NOT modify any ML/backend logic.
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pandas as pd
import re

from src.modeling.recommendation_engine import (
    get_mongodb_data,
    create_user_profile,
    get_contextual_recommendations,
    FEATURES,
)
from src.process_data import MONGO_URI, DB_NAME, COLLECTION_NAME

# ────────────────────────────────────────────
# App setup
# ────────────────────────────────────────────
app = FastAPI(title="Music Recommendation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────────────────
# Text cleaning for robust searching
# ────────────────────────────────────────────
def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'\(.*?\)', '', text)  # remove text between parentheses
    text = re.sub(r'-.*', '', text)      # remove text after dash (e.g. - Remastered)
    return text.strip()


# ────────────────────────────────────────────
# Cache: load data once at startup
# ────────────────────────────────────────────
_df: pd.DataFrame = pd.DataFrame()


@app.on_event("startup")
def _load_data():
    global _df
    _df = get_mongodb_data(MONGO_URI, DB_NAME, COLLECTION_NAME)
    if "_id" in _df.columns and "id" not in _df.columns:
        _df["id"] = _df["_id"].astype(str)
    elif "id" in _df.columns:
        _df["id"] = _df["id"].astype(str)
    # Drop Mongo ObjectId column so it doesn't cause serialisation issues
    if "_id" in _df.columns:
        _df.drop(columns=["_id"], inplace=True)
        
    # Create clean lookup columns to speed up matching
    if "name" in _df.columns:
        _df["clean_name"] = _df["name"].apply(clean_text)
    if "artist" in _df.columns:
        _df["clean_artist"] = _df["artist"].apply(clean_text)
        
    print(f"[API] Loaded {len(_df)} songs from data source.")


# ────────────────────────────────────────────
# Schemas
# ────────────────────────────────────────────
class RecommendationRequest(BaseModel):
    song_ids: List[str]
    emotion: str


class AutoRecommendationRequest(BaseModel):
    """Request body for Spotify auto-profile recommendations."""
    track_ids: List[str]
    emotion: str


class SongSeed(BaseModel):
    """A name+artist pair used to seed recommendations without needing a local ID."""
    name: str
    artist: str


class NameBasedRecommendationRequest(BaseModel):
    """Request body for text-based recommendations (name + artist)."""
    songs: List[SongSeed]
    emotion: str


class SongOut(BaseModel):
    id: str
    name: str
    artist: str
    emocion: str | None = None
    danceability: float = 0.0
    energy: float = 0.0
    valence: float = 0.0
    tempo: float = 0.0
    acousticness: float = 0.0


class RecommendationOut(BaseModel):
    id: str
    name: str
    artist: str
    similarity_score: float


# ────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────
@app.get("/api/songs/search", response_model=List[SongOut])
def search_songs(q: str = Query(..., min_length=2)):
    """Full-text search by song name or artist (max 20 results)."""
    search_terms = q.lower().split()
    mask = pd.Series([True] * len(_df), index=_df.index)
    for term in search_terms:
        mask = mask & (
            _df["name"].str.lower().str.contains(term, regex=False, na=False) |
            _df["artist"].str.lower().str.contains(term, regex=False, na=False)
        )
    results = _df[mask].head(20)
    return results.to_dict(orient="records")


@app.get("/api/emotions", response_model=List[str])
def get_emotions():
    """Return the list of distinct emotions available in the dataset."""
    emotion_col = "emocion" if "emocion" in _df.columns else "emotion"
    if emotion_col not in _df.columns:
        return []
    return sorted(_df[emotion_col].dropna().unique().tolist())


@app.post("/api/recommendations", response_model=List[RecommendationOut])
def recommend(body: RecommendationRequest):
    """Generate contextual recommendations based on seed songs + emotion."""
    if len(body.song_ids) < 1 or len(body.song_ids) > 5:
        raise HTTPException(status_code=400, detail="Provide 1-5 song IDs.")

    user_vector = create_user_profile(body.song_ids, _df)
    recs = get_contextual_recommendations(
        user_vector=user_vector,
        target_emotion=body.emotion,
        dataframe_base=_df,
        top_n=10,
        excluded_ids=body.song_ids,
    )
    return recs


# ────────────────────────────────────────────
# NEW: Endpoints for Spotify auto-profile
# ────────────────────────────────────────────
@app.post("/api/songs/by-ids", response_model=List[SongOut])
def get_songs_by_ids(track_ids: List[str]):
    """Find songs in the dataset that match the given track IDs."""
    id_col = "id" if "id" in _df.columns else "track_id"
    matched = _df[_df[id_col].isin(track_ids)].head(50)
    return matched.to_dict(orient="records")


class TrackMatch(BaseModel):
    name: str
    artist: str

@app.post("/api/songs/match-names")
def match_songs_by_names(tracks: List[TrackMatch]):
    """Match songs by name and artist using cleaned exact matches."""
    results = []
    
    # Increase lookup limit to 100 max to catch more library tracks
    for track in tracks[:100]:
        c_name = clean_text(track.name)
        c_artist = clean_text(track.artist)
        
        mask = _df["clean_name"] == c_name
        if c_artist:
            # We strictly enforce artist match to avoid false positives (e.g. cover songs)
            mask = mask & (_df["clean_artist"].str.contains(c_artist.split(',')[0].strip(), regex=False, na=False))
            
        matched = _df[mask]
        if not matched.empty:
            results.append(matched.iloc[0].to_dict())
                
    # Remove duplicates from the result list just in case multiple library matches hit the same local file
    unique_results = {r["id"] if "id" in r else r.get("_id"): r for r in results}.values()
    return list(unique_results)


@app.post("/api/recommendations/auto", response_model=List[RecommendationOut])
def recommend_auto(body: AutoRecommendationRequest):
    """Generate recommendations using a list of Spotify track IDs as
    the user profile. This replaces the manual 3-song selection for
    users logged in via Spotify."""
    if len(body.track_ids) < 1:
        raise HTTPException(status_code=400, detail="Provide at least 1 track ID.")

    # Try to match by ID first, then use whatever we find
    id_col = "id" if "id" in _df.columns else "track_id"
    matched_df = _df[_df[id_col].isin(body.track_ids)]

    if matched_df.empty:
        raise HTTPException(
            status_code=404,
            detail="None of the provided tracks were found in the dataset.",
        )

    # Build the user profile from ALL matched tracks using the shared 8-dim feature list
    present_features = [f for f in FEATURES if f in matched_df.columns]
    user_vector = matched_df[present_features].mean().values.tolist()

    recs = get_contextual_recommendations(
        user_vector=user_vector,
        target_emotion=body.emotion,
        dataframe_base=_df,
        top_n=10,
        excluded_ids=body.track_ids,
    )
    return recs
@app.post("/api/recommendations/by-names", response_model=List[RecommendationOut])
def recommend_by_names(body: NameBasedRecommendationRequest):
    """
    Acepta una lista de pares {name, artist} y resuelve cada uno contra el dataset
    mediante búsqueda de texto pre-limpiado en caché.
    Luego calcula el perfil de usuario y devuelve recomendaciones.
    """
    if not body.songs or len(body.songs) > 5:
        raise HTTPException(status_code=400, detail="Provide 1-5 songs.")

    id_col = "id" if "id" in _df.columns else "_id"
    matched_ids: List[str] = []

    for seed in body.songs:
        c_name = clean_text(seed.name)
        c_artist = clean_text(seed.artist)

        mask = (_df["clean_name"] == c_name)
        if c_artist:
            mask = mask & (_df["clean_artist"].str.contains(c_artist.split(',')[0].strip(), regex=False, na=False))
            
        hit = _df[mask].head(1)

        if not hit.empty:
            matched_ids.append(str(hit.iloc[0][id_col]))

    if not matched_ids:
        raise HTTPException(
            status_code=404,
            detail="None of the songs were found in the dataset. Check name and artist spelling.",
        )

    user_vector = create_user_profile(matched_ids, _df)
    recs = get_contextual_recommendations(
        user_vector=user_vector,
        target_emotion=body.emotion,
        dataframe_base=_df,
        top_n=10,
        excluded_ids=matched_ids,
    )
    return recs
