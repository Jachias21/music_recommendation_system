"""
FastAPI REST layer — wraps existing backend functions for the Angular frontend.
Does NOT modify any ML/backend logic.
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pandas as pd

from src.modeling.recommendation_engine import (
    get_mongodb_data,
    create_user_profile,
    get_contextual_recommendations,
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
    """Match songs by name and artist (case-insensitive). Used when Spotify track IDs
    don't directly match the dataset — fallback to name+artist matching."""
    results = []
    for track in tracks[:50]:  # Limit to 50 lookups
        mask_name = _df["name"].str.lower() == track.name.lower()
        matched_name = _df[mask_name]
        
        if not matched_name.empty:
            if track.artist:
                artist_first = track.artist.split(',')[0].strip().lower()
                mask_artist = matched_name["artist"].str.lower().str.contains(artist_first, regex=False, na=False)
                matched_fully = matched_name[mask_artist]
                if not matched_fully.empty:
                    results.append(matched_fully.iloc[0].to_dict())
            else:
                results.append(matched_name.iloc[0].to_dict())
    return results


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

    # Build the user profile from ALL matched tracks (not just 3)
    features = ["danceability", "energy", "valence", "tempo", "acousticness"]
    present_features = [f for f in features if f in matched_df.columns]
    user_vector = matched_df[present_features].mean().values.tolist()

    recs = get_contextual_recommendations(
        user_vector=user_vector,
        target_emotion=body.emotion,
        dataframe_base=_df,
        top_n=10,
    )
    return recs
