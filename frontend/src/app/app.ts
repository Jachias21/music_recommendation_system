import { Component } from '@angular/core';
import { RouterOutlet, ChildrenOutletContexts, Router, NavigationEnd } from '@angular/router';
import { Navbar } from './shared/components/navbar/navbar';
import { Sidebar } from './shared/components/sidebar/sidebar';
import { routeAnimations } from './shared/animations/route-animations';
import { AuthService } from './core/services/auth.service';
import { MoodService } from './core/services/mood.service';
import { filter } from 'rxjs/operators';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, Navbar, Sidebar],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  animations: [routeAnimations],
})
export class App {
  isOnboarding = false;

  constructor(
    private contexts: ChildrenOutletContexts,
    public auth: AuthService,
    public mood: MoodService,
    router: Router,
  ) {
    router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe((e: any) => {
      this.isOnboarding = e.urlAfterRedirects?.startsWith('/onboarding') ?? false;
    });
  }

  getRouteAnimationData() {
    return this.contexts.getContext('primary')?.route?.snapshot?.data?.['animation'];
  }
}
