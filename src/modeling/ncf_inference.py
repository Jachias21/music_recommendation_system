"""
NCF Inference Module (ONNX Runtime + FAISS)
============================================
Provides the NCFRecommender class for production-grade inference.

Architecture:
  - ONNX Runtime: Replaces PyTorch for model inference (lower latency, no GIL)
  - FAISS IndexFlatIP: Sub-millisecond nearest-neighbor retrieval
  - Hybrid Fallback: Audio-based surrogate resolution for OOV (Cold Start)

Artifacts expected:
  - models/ncf_model.onnx       → ONNX model (exported by 06_export_to_onnx.py)
  - models/item_embeddings.npy  → Pre-extracted item embedding matrix
  - models/item_encoder.pkl     → LabelEncoder for item ID mapping
  - models/user_encoder.pkl     → LabelEncoder for user ID mapping
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
import faiss
import onnxruntime as ort
from pathlib import Path

# Ensure project root is importable
root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))


# Default paths (relative to project root)
_BASE_DIR        = root_path
ONNX_PATH        = _BASE_DIR / "models" / "ncf_model.onnx"
EMBEDDINGS_PATH  = _BASE_DIR / "models" / "item_embeddings.npy"
ITEM_ENC_PATH    = _BASE_DIR / "models" / "item_encoder.pkl"
USER_ENC_PATH    = _BASE_DIR / "models" / "user_encoder.pkl"

# Legacy PyTorch paths (fallback if ONNX not yet exported)
WEIGHTS_PATH     = _BASE_DIR / "models" / "ncf_weights.pth"


class NCFRecommender:
    """
    Production-grade NCF recommender using ONNX Runtime + FAISS.

    Falls back to PyTorch weights if ONNX model is not available.

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
        # ── 1. Load item encoder ──────────────────────────────────────────
        if not ITEM_ENC_PATH.exists():
            raise FileNotFoundError(
                f"item_encoder.pkl not found at {ITEM_ENC_PATH}. Run train_ncf.py first."
            )
        with open(ITEM_ENC_PATH, "rb") as f:
            self.item_encoder = pickle.load(f)

        # Fast O(1) lookup: original_id -> matrix_index
        self._id_to_idx: dict = {
            str(class_): idx
            for idx, class_ in enumerate(self.item_encoder.classes_)
        }

        # ── 2. Load item embeddings ───────────────────────────────────────
        if EMBEDDINGS_PATH.exists():
            self.item_embeddings = np.load(str(EMBEDDINGS_PATH))
            print(f"[NCF] Item embeddings loaded from .npy: {self.item_embeddings.shape}")
        else:
            # Fallback: extract from PyTorch weights
            self.item_embeddings = self._extract_embeddings_from_pytorch()

        # ── 3. Initialize ONNX Runtime session ───────────────────────────
        self.ort_session = None
        if ONNX_PATH.exists():
            providers = ["CPUExecutionProvider"]
            # Use CoreML on macOS if available
            try:
                if "CoreMLExecutionProvider" in ort.get_available_providers():
                    providers.insert(0, "CoreMLExecutionProvider")
            except Exception:
                pass

            self.ort_session = ort.InferenceSession(str(ONNX_PATH), providers=providers)
            print(f"[NCF] ONNX Runtime session initialized. Providers: {self.ort_session.get_providers()}")
        else:
            print("[NCF] ONNX model not found. FAISS-only mode (no MLP scoring).")

        # ── 4. Build FAISS index ──────────────────────────────────────────
        self._build_faiss_index()

    # ──────────────────────────────────────────────────────────────────────
    def _extract_embeddings_from_pytorch(self) -> np.ndarray:
        """Fallback: extract embeddings directly from PyTorch weights."""
        import torch
        from src.modeling.ncf_model import NeuralCollaborativeFiltering

        num_items = len(self.item_encoder.classes_)
        num_users = 3001
        if USER_ENC_PATH.exists():
            with open(USER_ENC_PATH, "rb") as f:
                num_users = len(pickle.load(f).classes_)

        if not WEIGHTS_PATH.exists():
            raise FileNotFoundError(f"Neither ONNX nor PyTorch weights found.")

        model = NeuralCollaborativeFiltering(num_users=num_users, num_items=num_items)
        state = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model.eval()

        embeddings = model.item_embedding.weight.data.cpu().numpy()

        # Save for next time so we don't load PyTorch again
        np.save(str(EMBEDDINGS_PATH), embeddings)
        print(f"[NCF] Embeddings extracted from PyTorch and cached: {embeddings.shape}")
        return embeddings

    # ──────────────────────────────────────────────────────────────────────
    def _build_faiss_index(self):
        """
        Build FAISS IndexFlatIP over L2-normalized embeddings.
        Inner Product on normalized vectors == Cosine Similarity.
        """
        dim = self.item_embeddings.shape[1]

        norms = np.linalg.norm(self.item_embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-8)
        self._normalized_embeddings = (self.item_embeddings / norms).astype(np.float32)

        self._faiss_index = faiss.IndexFlatIP(dim)
        self._faiss_index.add(self._normalized_embeddings)
        print(f"[NCF] FAISS index built: {self._faiss_index.ntotal} vectors, dim={dim}")

    # ──────────────────────────────────────────────────────────────────────
    def _resolve_ids(self, raw_ids) -> np.ndarray:
        """Convert raw string IDs to embedding matrix indices (OOV-safe)."""
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
        Generate NCF recommendations for a cold-start user.

        Pipeline:
          1. Resolve seed IDs → embedding indices (with OOV hybrid fallback)
          2. Compute neuronal centroid from liked embeddings
          3. FAISS k-NN search for nearest items
          4. Post-filter by emotion, blacklist seeds
          5. Return top_n results with metadata
        """

        # ── Step 1: Resolve liked IDs ─────────────────────────────────────
        liked_indices = self._resolve_ids(user_liked_song_ids)
        id_col = "id" if "id" in candidate_df.columns else "track_id"

        if len(liked_indices) == 0:
            liked_indices = self._hybrid_fallback(
                user_liked_song_ids, target_emotion, candidate_df, id_col
            )

        if len(liked_indices) == 0:
            return []

        # ── Step 2: Compute neuronal centroid ─────────────────────────────
        liked_embeddings = self.item_embeddings[liked_indices]
        user_latent_vector = liked_embeddings.mean(axis=0)

        # L2-normalize for FAISS IP search
        norm = np.linalg.norm(user_latent_vector)
        if norm < 1e-8:
            return []
        query = (user_latent_vector / norm).reshape(1, -1).astype(np.float32)

        # ── Step 3: FAISS search ──────────────────────────────────────────
        fetch_k = min(top_n * 50, self._faiss_index.ntotal)
        scores, faiss_indices = self._faiss_index.search(query, fetch_k)
        scores = scores.flatten()
        faiss_indices = faiss_indices.flatten()

        # ── Step 4: Post-filter ───────────────────────────────────────────
        classes = self.item_encoder.classes_
        seed_set = {str(s) for s in user_liked_song_ids}
        emotion_col = "emocion" if "emocion" in candidate_df.columns else "emotion"

        # Pre-compute set of valid IDs for the target emotion
        emotion_mask = candidate_df[emotion_col].str.lower() == target_emotion.lower()
        valid_emotion_ids = set(candidate_df.loc[emotion_mask, id_col].astype(str).values)

        # ── Step 5: Collect results ───────────────────────────────────────
        recs = []
        for rank in range(len(faiss_indices)):
            idx = faiss_indices[rank]
            if idx < 0 or idx >= len(classes):
                continue

            item_id = str(classes[idx])

            if item_id in seed_set:
                continue

            if item_id not in valid_emotion_ids:
                continue

            # Lookup metadata
            row = candidate_df[candidate_df[id_col].astype(str) == item_id]
            if row.empty:
                continue

            row = row.iloc[0]
            recs.append({
                "id":               item_id,
                "name":             str(row.get("name", "")),
                "artist":           str(row.get("artist", "")),
                "similarity_score": float(round(scores[rank], 6)),
            })

            if len(recs) >= top_n:
                break

        return recs

    # ──────────────────────────────────────────────────────────────────────
    def _hybrid_fallback(self, user_liked_song_ids, target_emotion, candidate_df, id_col):
        """
        OOV Cold Start: find acoustically similar surrogates
        that the NCF model knows, then use those as proxy seeds.
        """
        print("[NCF] All seeds are OOV. Resolving via Audio Features Hybrid fallback...")
        try:
            from src.modeling.recommendation_engine import FEATURES
            from sklearn.metrics.pairwise import cosine_similarity

            seed_set = {str(s) for s in user_liked_song_ids}
            seed_df = candidate_df[candidate_df[id_col].astype(str).isin(seed_set)]

            if seed_df.empty:
                return np.array([], dtype=np.int64)

            present_features = [f for f in FEATURES if f in seed_df.columns]
            seed_audio_vector = seed_df[present_features].mean().values.reshape(1, -1)

            emotion_col = "emocion" if "emocion" in candidate_df.columns else "emotion"
            known_ids = set(self._id_to_idx.keys())
            known_candidates = candidate_df[
                (candidate_df[id_col].astype(str).isin(known_ids)) &
                (candidate_df[emotion_col].str.lower() == target_emotion.lower())
            ].copy()

            if not known_candidates.empty:
                known_candidates.dropna(subset=present_features, inplace=True)

                if not known_candidates.empty:
                    known_features = known_candidates[present_features].values
                    sim_scores = cosine_similarity(seed_audio_vector, known_features)[0]

                    top_idx = np.argsort(sim_scores)[::-1][:2]
                    surrogate_ids = known_candidates.iloc[top_idx][id_col].astype(str).tolist()
                    indices = self._resolve_ids(surrogate_ids)
                    print(f"[NCF] Hybrid surrogate activated. Replaced with known IDs: {surrogate_ids}")
                    return indices

        except Exception as e:
            import traceback
            print(f"[NCF] Hybrid fallback failed: {e}")
            traceback.print_exc()

        print("[NCF] Fallback failed. Returning empty.")
        return np.array([], dtype=np.int64)
