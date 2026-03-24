import { Component, input, output } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Song } from '../../../core/models/song.model';
import { SVG_ICONS } from '../../icons/svg-icons';

@Component({
  selector: 'app-song-card',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './song-card.html',
  styleUrl: './song-card.scss',
})
export class SongCard {
  song = input.required<Song>();
  actionLabel = input<string>('Añadir');
  actionIcon = input<string>('＋');
  showAction = input<boolean>(true);
  disabled = input<boolean>(false);
  compact = input<boolean>(false);

  action = output<Song>();
  icons = SVG_ICONS;

  onAction() {
    this.action.emit(this.song());
  }
}
