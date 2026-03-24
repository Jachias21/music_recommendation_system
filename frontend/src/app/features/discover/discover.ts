import { Component, inject, signal } from '@angular/core';
import { ApiService } from '../../core/services/api.service';
import { CartService } from '../../core/services/cart.service';
import { Song } from '../../core/models/song.model';
import { SongCard } from '../../shared/components/song-card/song-card';
import { Subject, debounceTime, distinctUntilChanged, switchMap, of } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { listStagger } from '../../shared/animations/route-animations';
import { SVG_ICONS } from '../../shared/icons/svg-icons';

@Component({
  selector: 'app-discover',
  standalone: true,
  imports: [SongCard],
  templateUrl: './discover.html',
  styleUrl: './discover.scss',
  animations: [listStagger],
})
export class Discover {
  private api = inject(ApiService);
  cart = inject(CartService);
  icons = SVG_ICONS;

  results = signal<Song[]>([]);
  query = signal('');
  isSearching = signal(false);
  hasSearched = signal(false);

  private search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(
        debounceTime(350),
        distinctUntilChanged(),
        switchMap((q) => {
          if (q.length < 2) {
            this.isSearching.set(false);
            this.hasSearched.set(false);
            return of([]);
          }
          this.isSearching.set(true);
          this.hasSearched.set(true);
          return this.api.searchSongs(q);
        }),
        takeUntilDestroyed()
      )
      .subscribe((res) => {
        this.results.set(res);
        this.isSearching.set(false);
      });
  }

  onSearch(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.query.set(val);
    this.search$.next(val);
  }

  addSong(song: Song): void {
    this.cart.add(song);
  }

  isInCart(songId: string): boolean {
    return this.cart.songs().some((s) => s.id === songId);
  }
}
