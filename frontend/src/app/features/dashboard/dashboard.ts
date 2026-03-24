import { Component, inject, signal, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { CartService } from '../../core/services/cart.service';
import { AuthService, AppUser } from '../../core/services/auth.service';
import { SpotifyService } from '../../core/services/spotify.service';
import { listStagger } from '../../shared/animations/route-animations';
import { SVG_ICONS, EMOTION_ICON_MAP } from '../../shared/icons/svg-icons';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

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
  private sanitizer = inject(DomSanitizer);
  cart = inject(CartService);
  spotify = inject(SpotifyService);
  icons = SVG_ICONS;

  emotions = signal<string[]>([]);
  selectedEmotion = signal<string>('');
  isGenerating = signal(false);
  isSpotifyUser = signal(false);

  ngOnInit(): void {
    // Load emotions
    this.api.getEmotions().subscribe((emotions) => {
      this.emotions.set(emotions);
      if (emotions.length > 0) {
        this.selectedEmotion.set(emotions[0]);
      }
    });

    // Detect Spotify user and auto-load their library
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

  selectEmotion(emotion: string): void {
    this.selectedEmotion.set(emotion);
  }

  /** Generate playlist — uses Spotify auto-profile or manual cart */
  generatePlaylist(): void {
    if (!this.selectedEmotion()) return;

    if (this.isSpotifyUser() && this.spotify.hasSpotifyData()) {
      this.generateFromSpotify();
    } else {
      this.generateFromCart();
    }
  }

  /** For Spotify users: use matched track IDs */
  private generateFromSpotify(): void {
    this.isGenerating.set(true);
    const matchedIds = this.spotify.matchedIds();

    this.api.getAutoRecommendations(matchedIds, this.selectedEmotion()).subscribe({
      next: (recs) => {
        this.isGenerating.set(false);
        this.router.navigate(['/playlist'], {
          state: { recommendations: recs, emotion: this.selectedEmotion() },
        });
      },
      error: () => {
        this.isGenerating.set(false);
      },
    });
  }

  /** For non-Spotify users: use manual cart of 3 songs */
  private generateFromCart(): void {
    if (this.cart.count() < 3) return;

    this.isGenerating.set(true);
    this.api.getRecommendations(this.cart.songIds(), this.selectedEmotion()).subscribe({
      next: (recs) => {
        this.isGenerating.set(false);
        this.router.navigate(['/playlist'], {
          state: { recommendations: recs, emotion: this.selectedEmotion() },
        });
      },
      error: () => {
        this.isGenerating.set(false);
      },
    });
  }

  /** Get SVG icon HTML for an emotion (sanitized for template binding) */
  getEmotionIcon(emotion: string): SafeHtml {
    const key = EMOTION_ICON_MAP[emotion.toLowerCase()] || 'MUSIC_NOTE';
    const svg = (SVG_ICONS as Record<string, string>)[key] || SVG_ICONS.MUSIC_NOTE;
    return this.sanitizer.bypassSecurityTrustHtml(svg);
  }

  /** Check if the generate button should be enabled */
  canGenerate(): boolean {
    if (!this.selectedEmotion()) return false;
    if (this.isGenerating()) return false;

    if (this.isSpotifyUser()) {
      return this.spotify.hasSpotifyData();
    }
    return this.cart.count() >= 3;
  }
}
