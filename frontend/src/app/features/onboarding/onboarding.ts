import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';
import { Song } from '../../core/models/song.model';

@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './onboarding.html',
  styleUrl: './onboarding.scss',
})
export class Onboarding implements OnInit {
  query = '';
  results: Song[] = [];
  selected: Song[] = [];
  isSearching = false;
  isSaving = false;
  errorMessage = '';

  private searchTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private auth: AuthService,
    private api: ApiService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    if (!this.auth.needsOnboarding()) {
      this.router.navigate(['/dashboard']);
    }
  }

  onQueryChange(): void {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    if (this.query.trim().length < 2) { this.results = []; return; }
    this.searchTimer = setTimeout(() => this.search(), 350);
  }

  search(): void {
    this.isSearching = true;
    this.api.searchSongs(this.query.trim()).subscribe({
      next: (songs) => { this.results = songs; this.isSearching = false; },
      error: () => { this.isSearching = false; },
    });
  }

  isSelected(song: Song): boolean {
    return this.selected.some((s) => s.id === song.id);
  }

  toggleSong(song: Song): void {
    if (this.isSelected(song)) {
      this.selected = this.selected.filter((s) => s.id !== song.id);
    } else if (this.selected.length < 3) {
      this.selected = [...this.selected, song];
    }
  }

  async save(): Promise<void> {
    if (this.selected.length < 1) return;
    this.isSaving = true;
    this.errorMessage = '';
    const user = this.auth.getCurrentUser();
    if (!user) return;
    try {
      await this.auth.completeOnboarding(user.id, this.selected.map((s) => s.id));
      this.router.navigate(['/dashboard']);
    } catch {
      this.errorMessage = 'Error al guardar. Intenta de nuevo.';
      this.isSaving = false;
    }
  }
}
