import { Component, inject, signal } from '@angular/core';
import { CartService } from '../../../core/services/cart.service';
import { ApiService } from '../../../core/services/api.service';
import { Song } from '../../../core/models/song.model';
import { SongCard } from '../song-card/song-card';
import { Subject, debounceTime, distinctUntilChanged, switchMap, of } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SVG_ICONS } from '../../icons/svg-icons';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [SongCard],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.scss',
})
export class Sidebar {
  cart = inject(CartService);
  private api = inject(ApiService);
  icons = SVG_ICONS;

  searchResults = signal<Song[]>([]);
  isSearching = signal(false);
  searchQuery = signal('');

  private searchSubject = new Subject<string>();

  constructor() {
    this.searchSubject
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((q) => {
          if (q.length < 2) {
            this.isSearching.set(false);
            return of([]);
          }
          this.isSearching.set(true);
          return this.api.searchSongs(q);
        }),
        takeUntilDestroyed()
      )
      .subscribe((results) => {
        this.searchResults.set(results);
        this.isSearching.set(false);
      });
  }

  onSearch(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.searchQuery.set(value);
    this.searchSubject.next(value);
  }

  addToCart(song: Song): void {
    this.cart.add(song);
  }

  removeFromCart(songId: string): void {
    this.cart.remove(songId);
  }
}
