import { Injectable, signal, computed } from '@angular/core';

export type Emotion = 'Alegre' | 'Triste' | 'Neutro';

@Injectable({ providedIn: 'root' })
export class MoodService {
  readonly emotion = signal<Emotion>('Neutro');

  readonly moodClass = computed(() => {
    const e = this.emotion();
    if (e === 'Alegre') return 'mood-alegre';
    if (e === 'Triste') return 'mood-triste';
    return 'mood-neutro';
  });

  setEmotion(e: Emotion) {
    this.emotion.set(e);
  }
}
