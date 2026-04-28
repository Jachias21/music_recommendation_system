import { Component, inject, signal, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Recommendation } from '../../core/models/song.model';
import { CartService } from '../../core/services/cart.service';
import { AuthService } from '../../core/services/auth.service';
import { SpotifyService } from '../../core/services/spotify.service';
import { listStagger } from '../../shared/animations/route-animations';
import { SVG_ICONS } from '../../shared/icons/svg-icons';

@Component({
  selector: 'app-playlist',
  standalone: true,
  templateUrl: './playlist.html',
  styleUrl: './playlist.scss',
  animations: [listStagger],
})
export class Playlist implements OnInit {
  private router = inject(Router);
  private auth = inject(AuthService);
  private spotifyService = inject(SpotifyService);
  cart = inject(CartService);
  icons = SVG_ICONS;

  recommendations = signal<Recommendation[]>([]);
  emotion = signal<string>('');
  isEmpty = signal(false);
  isExporting = signal(false);

  isSpotifyUser = signal(false);

  ngOnInit(): void {
    this.auth.user$.subscribe(user => {
      this.isSpotifyUser.set(user?.provider === 'spotify');
    });
    const nav = this.router.getCurrentNavigation();
    const state = nav?.extras?.state || history.state;

    if (state?.['recommendations'] && state['recommendations'].length > 0) {
      this.recommendations.set(state['recommendations']);
      this.emotion.set(state['emotion'] || '');
    } else {
      this.isEmpty.set(true);
    }
  }

  getScorePercent(score: number): number {
    return Math.round(score * 100);
  }

  getScoreColor(score: number): string {
    const pct = score * 100;
    if (pct >= 85) return 'var(--triste)';
    if (pct >= 70) return 'var(--success)';
    if (pct >= 50) return 'var(--warning)';
    return 'var(--text-secondary)';
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }

  startOver(): void {
    this.cart.clear();
    this.router.navigate(['/dashboard']);
  }

  async exportToSpotify(): Promise<void> {
    this.isExporting.set(true);
    try {
      if (this.isSpotifyUser()) {
        const url = await this.spotifyService.createPlaylist(
          this.recommendations().map(r => r.track_id || r.id),
          `Mi Playlist · Sound Lens — ${this.emotion()}`
        );
        window.open(url, '_blank');
      } else {
        // Fallback: Export to CSV
        const bom = "\uFEFF";
        const csvContent = "Título,Artista,Afinidad\n" + 
          this.recommendations().map(e => `"${e.name.replace(/"/g, '""')}","${e.artist.replace(/"/g, '""')}",${this.getScorePercent(e.similarity_score)}%`).join("\n");
        const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", `Playlist_SoundLens_${this.emotion()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch (err) {
      console.error('[Export] Failed to export playlist:', err);
    } finally {
      this.isExporting.set(false);
    }
  }
}
