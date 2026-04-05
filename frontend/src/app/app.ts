import { Component } from '@angular/core';
import { RouterOutlet, ChildrenOutletContexts } from '@angular/router';
import { Navbar } from './shared/components/navbar/navbar';
import { Sidebar } from './shared/components/sidebar/sidebar';
import { routeAnimations } from './shared/animations/route-animations';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, Navbar, Sidebar],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  animations: [routeAnimations],
})
export class App {
  constructor(
    private contexts: ChildrenOutletContexts,
    public auth: AuthService,
  ) { }

  getRouteAnimationData() {
    return this.contexts.getContext('primary')?.route?.snapshot?.data?.['animation'];
  }
}
