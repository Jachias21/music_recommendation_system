import { Component, inject, signal, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Recommendation } from '../../core/models/song.model';
import { CartService } from '../../core/services/cart.service';
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
  cart = inject(CartService);
  icons = SVG_ICONS;

  recommendations = signal<Recommendation[]>([]);
  emotion = signal<string>('');
  isEmpty = signal(false);

  ngOnInit(): void {
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
    if (pct >= 85) return 'var(--accent)';
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
}
