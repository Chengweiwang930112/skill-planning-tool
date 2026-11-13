import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import {
  SiApplicationHeaderComponent,
  SiHeaderBrandDirective,
  SiHeaderNavigationComponent,
  SiHeaderNavigationItemComponent,
} from '@siemens/element-ng/application-header';

@Component({
  selector: 'app-root',
  imports: [
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    SiApplicationHeaderComponent,
    SiHeaderBrandDirective,
    SiHeaderNavigationComponent,
    SiHeaderNavigationItemComponent,
  ],
  templateUrl: './app.html',
})
export class App {
  protected readonly title = 'Staff & Skill Planning';
}
