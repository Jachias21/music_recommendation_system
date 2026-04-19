import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Song, Recommendation, RecommendationRequest } from '../models/song.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient) {}

  searchSongs(query: string): Observable<Song[]> {
    const params = new HttpParams().set('q', query);
    return this.http.get<Song[]>(`${this.baseUrl}/songs/search`, { params });
  }

  getEmotions(): Observable<string[]> {
    return this.http.get<string[]>(`${this.baseUrl}/emotions`);
  }

  getRecommendations(songIds: string[], emotion: string, settings?: any): Observable<Recommendation[]> {
    const body: any = { song_ids: songIds, emotion };
    if (settings) {
      Object.assign(body, settings);
    }
    return this.http.post<Recommendation[]>(`${this.baseUrl}/recommendations`, body);
  }

  /** Get auto-recommendations using Spotify saved track IDs */
  getAutoRecommendations(trackIds: string[], emotion: string, settings?: any): Observable<Recommendation[]> {
    const body: any = { track_ids: trackIds, emotion };
    if (settings) {
      Object.assign(body, settings);
    }
    return this.http.post<Recommendation[]>(`${this.baseUrl}/recommendations/auto`, body);
  }

  /** Find songs in dataset matching given track IDs */
  getSongsByIds(trackIds: string[]): Observable<Song[]> {
    return this.http.post<Song[]>(`${this.baseUrl}/songs/by-ids`, trackIds);
  }
}
