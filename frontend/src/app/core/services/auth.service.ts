import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { BehaviorSubject } from 'rxjs';

export interface AppUser {
  id: string;
  display_name: string;
  email: string;
  images: { url: string }[];
  provider: 'spotify' | 'google' | 'local';
  onboarding_complete?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  /* ── Spotify config ───────────────────────── */
  private readonly SPOTIFY_CLIENT_ID = 'c8295b5e717042348ae0655ccad0091c';
  private readonly SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:4200/callback';
  private readonly SPOTIFY_SCOPES = 'user-read-private user-read-email user-library-read playlist-modify-public';
  private readonly SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize';
  private readonly SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token';

  /* ── Google config (placeholder) ──────────── */
  private readonly GOOGLE_CLIENT_ID = 'TU_GOOGLE_CLIENT_ID_AQUI';
  private readonly GOOGLE_REDIRECT_URI = 'https://localhost:4200/callback?provider=google';

  /* ── State ────────────────────────────────── */
  private userSubject = new BehaviorSubject<AppUser | null>(this.getStoredUser());
  user$ = this.userSubject.asObservable();

  constructor(private router: Router) { }

  /* ════════════════════════════════════════════
     PUBLIC API
     ════════════════════════════════════════════ */

  isLoggedIn(): boolean {
    const user = localStorage.getItem('app_user');
    if (!user) return false;

    const provider = JSON.parse(user).provider;
    if (provider === 'spotify') {
      const expiry = localStorage.getItem('spotify_token_expiry');
      return !!expiry && Date.now() < Number(expiry);
    }
    // Local and Google sessions don't expire in this demo
    return true;
  }

  /* ── Spotify login ────────────────────────── */

  async loginWithSpotify(): Promise<void> {
    const verifier = this.generateCodeVerifier(128);
    const challenge = await this.generateCodeChallenge(verifier);

    sessionStorage.setItem('code_verifier', verifier);
    sessionStorage.setItem('auth_provider', 'spotify');

    const params = new URLSearchParams({
      client_id: this.SPOTIFY_CLIENT_ID,
      response_type: 'code',
      redirect_uri: this.SPOTIFY_REDIRECT_URI,
      scope: this.SPOTIFY_SCOPES,
      code_challenge_method: 'S256',
      code_challenge: challenge,
    });

    window.location.href = `${this.SPOTIFY_AUTH_URL}?${params.toString()}`;
  }

  async handleSpotifyCallback(code: string): Promise<boolean> {
    const verifier = sessionStorage.getItem('code_verifier');
    if (!verifier) return false;

    try {
      const body = new URLSearchParams({
        client_id: this.SPOTIFY_CLIENT_ID,
        grant_type: 'authorization_code',
        code,
        redirect_uri: this.SPOTIFY_REDIRECT_URI,
        code_verifier: verifier,
      });

      const tokenRes = await fetch(this.SPOTIFY_TOKEN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });

      if (!tokenRes.ok) return false;

      const tokenData = await tokenRes.json();
      this.storeSpotifyToken(tokenData);
      sessionStorage.removeItem('code_verifier');
      sessionStorage.removeItem('auth_provider');

      await this.fetchSpotifyProfile(tokenData.access_token);
      return true;
    } catch {
      return false;
    }
  }

  /* ── Google login (placeholder) ───────────── */

  loginWithGoogle(): void {
    sessionStorage.setItem('auth_provider', 'google');

    const params = new URLSearchParams({
      client_id: this.GOOGLE_CLIENT_ID,
      redirect_uri: this.GOOGLE_REDIRECT_URI,
      response_type: 'code',
      scope: 'openid email profile',
      access_type: 'offline',
      prompt: 'consent',
    });

    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
  }

  async handleGoogleCallback(code: string): Promise<boolean> {
    // Placeholder: in production, exchange `code` for token via backend
    // For now, create a mock user to demonstrate the flow
    console.warn('[Auth] Google OAuth is in placeholder mode. Configure GOOGLE_CLIENT_ID to enable.');
    const user: AppUser = {
      id: 'google_placeholder',
      display_name: 'Usuario Google',
      email: 'usuario@gmail.com',
      images: [],
      provider: 'google',
    };
    this.setUser(user);
    return true;
  }

  /* ── Standard login (email/password) ──────── */

  async registerLocal(name: string, email: string, password: string): Promise<{ success: boolean; error?: string }> {
    try {
      const res = await fetch('http://localhost:8002/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { success: false, error: data.detail || 'Error al registrar.' };
      }
      const user: AppUser = {
        id: data.id,
        display_name: data.name,
        email: data.email,
        images: [],
        provider: 'local',
        onboarding_complete: data.onboarding_complete,
      };
      this.setUser(user);
      return { success: true };
    } catch {
      return { success: false, error: 'No se pudo conectar al servidor. Asegúrate de que el backend está activo.' };
    }
  }

  async loginLocal(email: string, password: string): Promise<{ success: boolean; error?: string }> {
    try {
      const res = await fetch('http://localhost:8002/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        return { success: false, error: data.detail || 'Error al iniciar sesión.' };
      }
      const user: AppUser = {
        id: data.id,
        display_name: data.name,
        email: data.email,
        images: [],
        provider: 'local',
        onboarding_complete: data.onboarding_complete,
      };
      this.setUser(user);
      return { success: true };
    } catch {
      return { success: false, error: 'No se pudo conectar al servidor. Asegúrate de que el backend está activo.' };
    }
  }

  async completeOnboarding(userId: string, seedSongIds: string[]): Promise<void> {
    await fetch(`http://localhost:8002/api/users/${userId}/onboarding`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed_song_ids: seedSongIds }),
    });
    const user = this.userSubject.getValue();
    if (user) {
      const updated = { ...user, onboarding_complete: true };
      this.setUser(updated);
    }
  }

  needsOnboarding(): boolean {
    const user = this.userSubject.getValue();
    return !!user && user.provider === 'local' && user.onboarding_complete === false;
  }

  getCurrentUser(): AppUser | null {
    return this.userSubject.getValue();
  }

  /* ── Logout ───────────────────────────────── */

  logout(): void {
    localStorage.removeItem('app_user');
    localStorage.removeItem('spotify_access_token');
    localStorage.removeItem('spotify_refresh_token');
    localStorage.removeItem('spotify_token_expiry');
    localStorage.removeItem('spotify_saved_tracks');
    localStorage.removeItem('spotify_matched_songs');
    this.userSubject.next(null);
    this.router.navigate(['/login']);
  }

  getAccessToken(): string | null {
    return localStorage.getItem('spotify_access_token');
  }

  /* ════════════════════════════════════════════
     PRIVATE HELPERS
     ════════════════════════════════════════════ */

  private setUser(user: AppUser): void {
    localStorage.setItem('app_user', JSON.stringify(user));
    this.userSubject.next(user);
  }

  private storeSpotifyToken(data: any): void {
    localStorage.setItem('spotify_access_token', data.access_token);
    if (data.refresh_token) {
      localStorage.setItem('spotify_refresh_token', data.refresh_token);
    }
    const expiry = Date.now() + data.expires_in * 1000;
    localStorage.setItem('spotify_token_expiry', expiry.toString());
  }

  private async fetchSpotifyProfile(token: string): Promise<void> {
    const res = await fetch('https://api.spotify.com/v1/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const spotifyUser = await res.json();
      const user: AppUser = {
        id: spotifyUser.id,
        display_name: spotifyUser.display_name,
        email: spotifyUser.email,
        images: spotifyUser.images || [],
        provider: 'spotify',
      };
      this.setUser(user);
    }
  }

  private getStoredUser(): AppUser | null {
    const raw = localStorage.getItem('app_user');
    return raw ? JSON.parse(raw) : null;
  }

  /* ── PKCE utils ───────────────────────────── */

  private generateCodeVerifier(length: number): string {
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    const values = crypto.getRandomValues(new Uint8Array(length));
    return Array.from(values, (v) => possible[v % possible.length]).join('');
  }

  private async generateCodeChallenge(verifier: string): Promise<string> {
    const data = new TextEncoder().encode(verifier);
    const digest = await crypto.subtle.digest('SHA-256', data);
    return btoa(String.fromCharCode(...new Uint8Array(digest)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  }
}
