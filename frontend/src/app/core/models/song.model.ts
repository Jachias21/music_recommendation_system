/** Song model matching the API response */
export interface Song {
  id: string;
  name: string;
  artist: string;
  emocion?: string;
  danceability: number;
  energy: number;
  valence: number;
  tempo: number;
  acousticness: number;
}

/** Recommendation result */
export interface Recommendation {
  id: string;
  name: string;
  artist: string;
  similarity_score: number;
}

/** POST body for /api/recommendations */
export interface RecommendationRequest {
  song_ids: string[];
  emotion: string;
}

/** A name+artist pair for text-based recommendations */
export interface SongSeed {
  name: string;
  artist: string;
}
