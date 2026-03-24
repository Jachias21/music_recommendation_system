import { Component } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { SVG_ICONS } from '../../shared/icons/svg-icons';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login {
  email = '';
  password = '';
  errorMessage = '';
  isLoading = false;
  icons = SVG_ICONS;

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  loginWithSpotify(): void {
    this.auth.loginWithSpotify();
  }

  loginWithGoogle(): void {
    this.auth.loginWithGoogle();
  }

  loginLocal(): void {
    this.errorMessage = '';

    if (!this.email || !this.password) {
      this.errorMessage = 'Completa todos los campos.';
      return;
    }

    this.isLoading = true;
    const result = this.auth.loginLocal(this.email, this.password);
    this.isLoading = false;

    if (result.success) {
      this.router.navigate(['/dashboard']);
    } else {
      this.errorMessage = result.error || 'Error al iniciar sesión.';
    }
  }
}
