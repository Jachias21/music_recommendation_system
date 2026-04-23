import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { JsonPipe } from '@angular/common';

interface SettingsData {
  serendipity: number;
  novelty: number;
  instrumentalness: number;
  diversity: 'balanced' | 'focused' | 'wide';
}

const DEFAULTS: SettingsData = {
  serendipity: 75,
  novelty: 40,
  instrumentalness: 20,
  diversity: 'balanced',
};

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule, JsonPipe],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class Settings {
  saved = signal(false);

  values = signal<SettingsData>(this.loadFromStorage());

  private loadFromStorage(): SettingsData {
    try {
      const raw = localStorage.getItem('sonicLensSettings');
      if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
    } catch { /* ignore */ }
    return { ...DEFAULTS };
  }

  apply(): void {
    localStorage.setItem('sonicLensSettings', JSON.stringify(this.values()));
    this.saved.set(true);
    setTimeout(() => this.saved.set(false), 2000);
  }

  reset(): void {
    this.values.set({ ...DEFAULTS });
    localStorage.removeItem('sonicLensSettings');
  }

  updateSlider(key: keyof SettingsData, event: Event): void {
    const val = +(event.target as HTMLInputElement).value;
    this.values.update(v => ({ ...v, [key]: val }));
    this.apply(); // Auto-save
  }

  setDiversity(val: SettingsData['diversity']): void {
    this.values.update(v => ({ ...v, diversity: val }));
    this.apply(); // Auto-save
  }
}
