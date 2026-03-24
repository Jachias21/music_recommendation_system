import { Injectable, signal, computed } from '@angular/core';
import { Song } from '../models/song.model';

@Injectable({ providedIn: 'root' })
export class CartService {
  private readonly MAX_SONGS = 3;

  /** Reactive signals for the cart */
  readonly songs = signal<Song[]>([]);
  readonly count = computed(() => this.songs().length);
  readonly isFull = computed(() => this.songs().length >= this.MAX_SONGS);
  readonly progress = computed(() => this.songs().length / this.MAX_SONGS);
  readonly songIds = computed(() => this.songs().map((s) => s.id));

  add(song: Song): boolean {
    if (this.isFull() || this.songs().some((s) => s.id === song.id)) {
      return false;
    }
    this.songs.update((prev) => [...prev, song]);
    return true;
  }

  remove(songId: string): void {
    this.songs.update((prev) => prev.filter((s) => s.id !== songId));
  }

  clear(): void {
    this.songs.set([]);
  }
}
