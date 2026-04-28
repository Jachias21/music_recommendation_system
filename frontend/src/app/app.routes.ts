import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./features/login/login').then((m) => m.Login),
  },
  {
    path: 'callback',
    loadComponent: () =>
      import('./features/callback/callback').then((m) => m.Callback),
  },
  {
    path: 'register',
    loadComponent: () =>
      import('./features/register/register').then((m) => m.Register),
  },
  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full',
  },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./features/dashboard/dashboard').then((m) => m.Dashboard),
    data: { animation: 'Dashboard' },
    canActivate: [authGuard],
  },
  {
    path: 'discover',
    loadComponent: () =>
      import('./features/discover/discover').then((m) => m.Discover),
    data: { animation: 'Discover' },
    canActivate: [authGuard],
  },
  {
    path: 'playlist',
    loadComponent: () =>
      import('./features/playlist/playlist').then((m) => m.Playlist),
    data: { animation: 'Playlist' },
    canActivate: [authGuard],
  },
  {
    path: 'analysis',
    loadComponent: () =>
      import('./features/analysis/analysis').then((m) => m.Analysis),
    data: { animation: 'Analysis' },
    canActivate: [authGuard],
  },
  {
    path: 'settings',
    loadComponent: () =>
      import('./features/settings/settings').then((m) => m.Settings),
    data: { animation: 'Settings' },
    canActivate: [authGuard],
  },
  {
    path: 'onboarding',
    loadComponent: () =>
      import('./features/onboarding/onboarding').then((m) => m.Onboarding),
    canActivate: [authGuard],
  },
];
