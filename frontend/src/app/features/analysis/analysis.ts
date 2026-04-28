import { Component, inject, computed } from '@angular/core';
import { CartService } from '../../core/services/cart.service';
import { MoodService } from '../../core/services/mood.service';

interface RadarPoint { x: number; y: number; }

const CENTER = 120;
const RADIUS = 90;
const AXES = ['Dance', 'Energy', 'Valence', 'Acoustic', 'Tempo'];

function polarToXY(angle: number, r: number): RadarPoint {
  const rad = (angle - 90) * (Math.PI / 180);
  return { x: CENTER + r * Math.cos(rad), y: CENTER + r * Math.sin(rad) };
}

function buildPolygon(values: number[]): string {
  return values
    .map((v, i) => {
      const angle = (360 / values.length) * i;
      const pt = polarToXY(angle, v * RADIUS);
      return `${pt.x},${pt.y}`;
    })
    .join(' ');
}

function buildAxisLine(i: number, total: number): string {
  const pt = polarToXY((360 / total) * i, RADIUS);
  return `${CENTER},${CENTER} ${pt.x},${pt.y}`;
}

function axisLabel(i: number, total: number, label: string): RadarPoint & { label: string } {
  const pt = polarToXY((360 / total) * i, RADIUS + 18);
  return { ...pt, label };
}

@Component({
  selector: 'app-analysis',
  standalone: true,
  templateUrl: './analysis.html',
  styleUrl: './analysis.scss',
})
export class Analysis {
  cart = inject(CartService);
  mood = inject(MoodService);

  readonly PLACEHOLDER = [0.7, 0.6, 0.8, 0.4, 0.65];

  readonly values = computed<number[]>(() => {
    const songs = this.cart.songs();
    if (songs.length === 0) return this.PLACEHOLDER;
    const avg = (key: keyof typeof songs[0]) =>
      songs.reduce((s, song) => s + (song[key] as number || 0), 0) / songs.length;
    return [
      avg('danceability'),
      avg('energy'),
      avg('valence'),
      avg('acousticness'),
      Math.min(avg('tempo') / 200, 1),
    ];
  });

  readonly polygon = computed(() => buildPolygon(this.values()));

  readonly gridLines = [0.25, 0.5, 0.75, 1].map(r =>
    AXES.map((_, i) => polarToXY((360 / AXES.length) * i, r * RADIUS))
      .map(p => `${p.x},${p.y}`).join(' ')
  );

  readonly axisLines = AXES.map((_, i) => buildAxisLine(i, AXES.length));
  readonly labels = AXES.map((label, i) => axisLabel(i, AXES.length, label));

  readonly metrics = computed(() => {
    const v = this.values();
    return [
      { label: 'Energía', value: v[1], pct: Math.round(v[1] * 100) },
      { label: 'Tempo',   value: v[4], pct: Math.round(v[4] * 100) },
    ];
  });

  readonly CENTER = CENTER;
  readonly RADIUS = RADIUS;
}
