import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { SpotifyService } from '../../core/services/spotify.service';

@Component({
  selector: 'app-callback',
  standalone: true,
  templateUrl: './callback.html',
  styleUrl: './callback.scss',
})
export class Callback implements OnInit {
  error = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private auth: AuthService,
    private spotify: SpotifyService,
  ) {}

  async ngOnInit(): Promise<void> {
    const code = this.route.snapshot.queryParamMap.get('code');
    const errorParam = this.route.snapshot.queryParamMap.get('error');
    const provider = this.route.snapshot.queryParamMap.get('provider')
                  || sessionStorage.getItem('auth_provider')
                  || 'spotify';

    if (errorParam || !code) {
      this.error = true;
      setTimeout(() => this.router.navigate(['/login']), 3000);
      return;
    }

    let success = false;

    if (provider === 'google') {
      success = await this.auth.handleGoogleCallback(code);
    } else {
      success = await this.auth.handleSpotifyCallback(code);

      // After successful Spotify auth, pre-load saved tracks
      if (success) {
        this.spotify.loadSavedTracks();
      }
    }

    if (success) {
      this.router.navigate(['/dashboard']);
    } else {
      this.error = true;
      setTimeout(() => this.router.navigate(['/login']), 3000);
    }
  }
}
