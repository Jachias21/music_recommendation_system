import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Song } from '../models/song.model';
import { AuthService } from './auth.service';

export interface SpotifySavedTrack {
  id: string;
  name: string;
  artist: string;
  album: string;
  uri: string;
}

@Injectable({ providedIn: 'root' })
export class SpotifyService {
  private readonly SPOTIFY_API = 'https://api.spotify.com/v1';
  private readonly BACKEND_API = 'http://localhost:8000/api';

  /** Reactive state */
  readonly savedTracks = signal<SpotifySavedTrack[]>([]);
  readonly matchedSongs = signal<Song[]>([]);
  readonly isLoading = signal(false);
  readonly isLoaded = signal(false);

  readonly hasSpotifyData = computed(() => this.matchedSongs().length > 0);
  readonly matchedIds = computed(() => this.matchedSongs().map(s => s.id));

  constructor(
    private http: HttpClient,
    private auth: AuthService,
  ) {
    // Try to restore from localStorage
    this.restoreFromStorage();
  }

  /**
   * Fetch user's saved tracks from Spotify API and then match them
   * against our dataset via the backend.
   */
  async loadSavedTracks(): Promise<void> {
    const token = this.auth.getAccessToken();
    if (!token) return;

    this.isLoading.set(true);

    try {
      // Step 1: Fetch saved tracks from Spotify (up to 50)
      const res = await fetch(`${this.SPOTIFY_API}/me/tracks?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        console.error('[Spotify] Failed to fetch saved tracks:', res.status);
        this.isLoading.set(false);
        return;
      }

      const data = await res.json();
      const tracks: SpotifySavedTrack[] = data.items.map((item: any) => ({
        id: item.track.id,
        name: item.track.name,
        artist: item.track.artists.map((a: any) => a.name).join(', '),
        album: item.track.album.name,
        uri: item.track.uri,
      }));

      this.savedTracks.set(tracks);
      localStorage.setItem('spotify_saved_tracks', JSON.stringify(tracks));

      // Step 2: Match against our dataset
      await this.matchTracksWithDataset(tracks);

      this.isLoaded.set(true);
    } catch (err) {
      console.error('[Spotify] Error loading saved tracks:', err);
    } finally {
      this.isLoading.set(false);
    }
  }

  /**
   * Try to match Spotify tracks against our dataset.
   * First by track ID, then fallback to name matching.
   */
  private async matchTracksWithDataset(tracks: SpotifySavedTrack[]): Promise<void> {
    try {
      // Try matching by Spotify track IDs
      const trackIds = tracks.map(t => t.id);
      const byIdRes = await fetch(`${this.BACKEND_API}/songs/by-ids`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(trackIds),
      });

      let matched: Song[] = [];
      if (byIdRes.ok) {
        matched = await byIdRes.json();
      }

      // If no ID matches, fallback to name matching
      if (matched.length === 0) {
        const names = tracks.map(t => t.name);
        const byNameRes = await fetch(`${this.BACKEND_API}/songs/match-names`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(names),
        });

        if (byNameRes.ok) {
          matched = await byNameRes.json();
        }
      }

      this.matchedSongs.set(matched);
      localStorage.setItem('spotify_matched_songs', JSON.stringify(matched));
      console.log(`[Spotify] Matched ${matched.length} songs with dataset.`);
    } catch (err) {
      console.error('[Spotify] Error matching tracks:', err);
    }
  }

  /**
   * Restore previously fetched data from localStorage.
   */
  private restoreFromStorage(): void {
    try {
      const savedRaw = localStorage.getItem('spotify_saved_tracks');
      if (savedRaw) {
        this.savedTracks.set(JSON.parse(savedRaw));
      }

      const matchedRaw = localStorage.getItem('spotify_matched_songs');
      if (matchedRaw) {
        const matched = JSON.parse(matchedRaw);
        this.matchedSongs.set(matched);
        if (matched.length > 0) {
          this.isLoaded.set(true);
        }
      }
    } catch {
      // Ignore parse errors
    }
  }

  /**
   * Clear all stored Spotify data (called on logout).
   */
  clearData(): void {
    this.savedTracks.set([]);
    this.matchedSongs.set([]);
    this.isLoaded.set(false);
    localStorage.removeItem('spotify_saved_tracks');
    localStorage.removeItem('spotify_matched_songs');
  }
}
