"""
NCF Inference Module
====================
Provides the NCFRecommender class which loads pre-trained weights and exposes
a high-level get_recommendations() method for the FastAPI layer.

Cold Start strategy: Item-to-Item Latent Similarity.
  - We never query the user_embedding (user not in training set).
  - Instead we compute a "Neuronal Centroid" as the mean of the item
    embeddings of songs the user has already liked.
  - Candidates are ranked by Cosine Similarity against this centroid.
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
from pathlib import Path

# Ensure project root is importable
root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from src.modeling.ncf_model import NeuralCollaborativeFiltering


# Default paths (relative to project root)
_BASE_DIR = root_path
WEIGHTS_PATH    = _BASE_DIR / "models" / "ncf_weights.pth"
ITEM_ENC_PATH   = _BASE_DIR / "models" / "item_encoder.pkl"
USER_ENC_PATH   = _BASE_DIR / "models" / "user_encoder.pkl"


class NCFRecommender:
    """
    High-level wrapper around the trained NeuralCollaborativeFiltering model.

    Usage:
        recommender = NCFRecommender()
        recs = recommender.get_recommendations(
            user_liked_song_ids=["id1", "id2"],
            target_emotion="alegre",
            candidate_df=df,
            top_n=10,
        )
    """

    def __init__(self):
        import torch

        # ── 1. Load encoders ──────────────────────────────────────────────
        if not ITEM_ENC_PATH.exists():
            raise FileNotFoundError(f"item_encoder.pkl not found at {ITEM_ENC_PATH}. Run train_ncf.py first.")
        with open(ITEM_ENC_PATH, "rb") as f:
            self.item_encoder = pickle.load(f)

        # Build a fast O(1) lookup: original_id -> matrix_index
        self._id_to_idx: dict = {
            str(class_): idx
            for idx, class_ in enumerate(self.item_encoder.classes_)
        }

        num_items = len(self.item_encoder.classes_)

        # Detect num_users from user encoder if available, else use a safe default
        num_users = 3001
        if USER_ENC_PATH.exists():
            with open(USER_ENC_PATH, "rb") as f:
                user_enc = pickle.load(f)
            num_users = len(user_enc.classes_)

        # ── 2. Load model weights ─────────────────────────────────────────
        if not WEIGHTS_PATH.exists():
            raise FileNotFoundError(f"ncf_weights.pth not found at {WEIGHTS_PATH}. Run train_ncf.py first.")

        self.model = NeuralCollaborativeFiltering(
            num_users=num_users,
            num_items=num_items,
        )
        state = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
        self.model.load_state_dict(state)
        self.model.eval()

        # ── 3. Extract & cache item embedding matrix ──────────────────────
        # Shape: (num_items, embedding_dim) as float32 NumPy array
        self.item_embeddings: np.ndarray = (
            self.model.item_embedding.weight.data.cpu().numpy()
        )
        print(f"[NCF] Model loaded. Item embedding matrix: {self.item_embeddings.shape}")

    # ──────────────────────────────────────────────────────────────────────
    def _resolve_ids(self, raw_ids) -> np.ndarray:
        """
        Convert raw MongoDB string IDs to embedding matrix indices,
        silently ignoring any Out-Of-Vocabulary (OOV) entries.
        """
        indices = []
        for rid in raw_ids:
            idx = self._id_to_idx.get(str(rid))
            if idx is not None:
                indices.append(idx)
        return np.array(indices, dtype=np.int64)

    # ──────────────────────────────────────────────────────────────────────
    def get_recommendations(
        self,
        user_liked_song_ids,
        target_emotion: str,
        candidate_df: pd.DataFrame,
        top_n: int = 10,
    ) -> list:
        """
        Generate NCF-based recommendations for a cold-start user.

        Args:
            user_liked_song_ids: List/iterable of raw MongoDB song IDs the user likes.
            target_emotion: Emotion string to pre-filter candidates (e.g. "alegre").
            candidate_df: The full in-memory DataFrame loaded from MongoDB.
            top_n: Number of recommendations to return.

        Returns:
            List of dicts with keys: id, name, artist, similarity_score.
        """

        # ── Step 1: Resolve liked IDs to matrix indices ───────────────────
        liked_indices = self._resolve_ids(user_liked_song_ids)
        id_col = "id" if "id" in candidate_df.columns else "track_id"

        if len(liked_indices) == 0:
            print("[NCF] All seeds are OOV. Resolving via Audio Features Hybrid fallback...")
            try:
                from src.modeling.recommendation_engine import FEATURES
                from sklearn.metrics.pairwise import cosine_similarity
                
                seed_set = {str(s) for s in user_liked_song_ids}
                seed_df = candidate_df[candidate_df[id_col].astype(str).isin(seed_set)]
                
                if seed_df.empty:
                    return []
                    
                present_features = [f for f in FEATURES if f in seed_df.columns]
                seed_audio_vector = seed_df[present_features].mean().values.reshape(1, -1)
                
                # Filtrar solo canciones que la red neuronal SI conozca Y DE LA MISMA EMOCION
                emotion_col = "emocion" if "emocion" in candidate_df.columns else "emotion"
                known_ids = set(self._id_to_idx.keys())
                known_candidates = candidate_df[
                    (candidate_df[id_col].astype(str).isin(known_ids)) &
                    (candidate_df[emotion_col].str.lower() == target_emotion.lower())
                ].copy()
                
                if not known_candidates.empty:
                    # Drop rows missing features
                    known_candidates.dropna(subset=present_features, inplace=True)
                    
                    if not known_candidates.empty:
                        known_features = known_candidates[present_features].values
                        sim_scores = cosine_similarity(seed_audio_vector, known_features)[0]
                        
                        top_idx = np.argsort(sim_scores)[::-1][:2]
                        surrogate_ids = known_candidates.iloc[top_idx][id_col].astype(str).tolist()
                        liked_indices = self._resolve_ids(surrogate_ids)
                        print(f"[NCF] Hybrid surrogate activated. Replaced with known IDs: {surrogate_ids}")
            except Exception as e:
                import traceback
                print(f"[NCF] Hybrid fallback failed: {e}")
                traceback.print_exc()

        # Si aún así falla
        if len(liked_indices) == 0:
            print("[NCF] Fallback failed. Returning empty.")
            return []

        # ── Step 2: Compute the Neuronal Centroid (user latent vector) ────
        liked_embeddings = self.item_embeddings[liked_indices]           # (K, 64)
        user_latent_vector = liked_embeddings.mean(axis=0, keepdims=True) # (1, 64)

        # ── Step 3: Filter candidates by emotion ──────────────────────────
        emotion_col = "emocion" if "emocion" in candidate_df.columns else "emotion"
        id_col      = "id"      if "id"      in candidate_df.columns else "track_id"

        filtered = candidate_df[
            candidate_df[emotion_col].str.lower() == target_emotion.lower()
        ].copy()

        # ── Step 4: Blacklisting – remove seed songs ─────────────────────
        seed_set = {str(s) for s in user_liked_song_ids}
        filtered = filtered[~filtered[id_col].astype(str).isin(seed_set)]

        if filtered.empty:
            return []

        # ── Step 5: Resolve candidate IDs to embedding indices ────────────
        candidate_raw_ids = filtered[id_col].astype(str).tolist()
        candidate_indices = self._resolve_ids(candidate_raw_ids)

        if len(candidate_indices) == 0:
            print("[NCF] No candidate embeddings found. Returning empty.")
            return []

        # Map back to DataFrame rows (some candidates may be OOV)
        known_mask = np.isin(
            filtered[id_col].astype(str).values,
            [str(self.item_encoder.classes_[i]) for i in candidate_indices],
        )
        filtered_known = filtered[known_mask].reset_index(drop=True)

        # ── Step 6: Vectorized Cosine Similarity ──────────────────────────
        candidate_matrix = self.item_embeddings[candidate_indices]       # (N, 64)

        # Cosine similarity: dot(A, b) / (||A|| * ||b||)
        dot_products   = candidate_matrix @ user_latent_vector.T          # (N, 1)
        norms_cand     = np.linalg.norm(candidate_matrix, axis=1, keepdims=True)  # (N, 1)
        norm_user      = np.linalg.norm(user_latent_vector)

        epsilon = 1e-8  # avoid division by zero
        scores = (dot_products / (norms_cand * norm_user + epsilon)).flatten()  # (N,)

        # ── Step 7: Sort and build output ────────────────────────────────
        top_indices = np.argsort(scores)[::-1][:top_n]

        recs = []
        for i in top_indices:
            row = filtered_known.iloc[i]
            recs.append({
                "id":               str(row.get(id_col, "")),
                "name":             str(row.get("name", "")),
                "artist":           str(row.get("artist", "")),
                "similarity_score": float(round(scores[i], 6)),
            })

        return recs
