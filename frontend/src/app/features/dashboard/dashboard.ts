import { Component, inject, signal, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { CartService } from '../../core/services/cart.service';
import { AuthService, AppUser } from '../../core/services/auth.service';
import { SpotifyService } from '../../core/services/spotify.service';
import { MoodService, Emotion } from '../../core/services/mood.service';
import { listStagger } from '../../shared/animations/route-animations';
import { SVG_ICONS } from '../../shared/icons/svg-icons';

const ALLOWED_EMOTIONS: Emotion[] = ['Alegre', 'Triste', 'Neutro'];

const COMMUNITY_PLAYLISTS = [
  { title: 'Neon Pulse Drive', plays: '1.2k', mood: 'Alegre' },
  { title: 'Ethereal Static',  plays: '842',  mood: 'Neutro' },
  { title: 'Abyssal Chill',    plays: '3.5k', mood: 'Triste' },
];

@Component({
  selector: 'app-dashboard',
  standalone: true,
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
  animations: [listStagger],
})
export class Dashboard implements OnInit {
  private api = inject(ApiService);
  private router = inject(Router);
  private auth = inject(AuthService);
  cart = inject(CartService);
  spotify = inject(SpotifyService);
  mood = inject(MoodService);
  icons = SVG_ICONS;

  emotions = ALLOWED_EMOTIONS;
  selectedEmotion = signal<Emotion>('Neutro');
  isGenerating = signal(false);
  isSpotifyUser = signal(false);
  community = COMMUNITY_PLAYLISTS;

  ngOnInit(): void {
    this.auth.user$.subscribe((user: AppUser | null) => {
      if (user?.provider === 'spotify') {
        this.isSpotifyUser.set(true);
        if (!this.spotify.isLoaded()) {
          this.spotify.loadSavedTracks();
        }
      } else {
        this.isSpotifyUser.set(false);
      }
    });
  }

  selectEmotion(emotion: Emotion): void {
    this.selectedEmotion.set(emotion);
    this.mood.setEmotion(emotion);
  }

  generatePlaylist(): void {
    if (!this.selectedEmotion()) return;
    if (this.isSpotifyUser() && this.spotify.hasSpotifyData()) {
      this.generateFromSpotify();
    } else {
      this.generateFromCart();
    }
  }

  private getSettings(): any {
    try {
      const raw = localStorage.getItem('sonicLensSettings');
      if (raw) return JSON.parse(raw);
    } catch { /* ignore */ }
    return undefined;
  }

  private generateFromSpotify(): void {
    this.isGenerating.set(true);
    this.api.getAutoRecommendations(this.spotify.matchedIds(), this.selectedEmotion(), this.getSettings()).subscribe({
      next: (recs) => {
        this.isGenerating.set(false);
        this.router.navigate(['/playlist'], {
          state: { recommendations: recs, emotion: this.selectedEmotion() },
        });
      },
      error: () => this.isGenerating.set(false),
    });
  }

  private generateFromCart(): void {
    if (this.cart.count() < 3) return;
    this.isGenerating.set(true);
    this.api.getRecommendations(this.cart.songIds(), this.selectedEmotion(), this.getSettings()).subscribe({
      next: (recs) => {
        this.isGenerating.set(false);
        this.router.navigate(['/playlist'], {
          state: { recommendations: recs, emotion: this.selectedEmotion() },
        });
      },
      error: () => this.isGenerating.set(false),
    });
  }

  canGenerate(): boolean {
    if (!this.selectedEmotion() || this.isGenerating()) return false;
    if (this.isSpotifyUser()) return this.spotify.hasSpotifyData();
    return this.cart.count() >= 3;
  }

  moodClass(emotion: string): string {
    if (emotion === 'Alegre') return 'alegre';
    if (emotion === 'Triste') return 'triste';
    return 'neutro';
  }
}
