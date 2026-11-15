import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import {
  SiApplicationHeaderComponent,
  SiHeaderActionsDirective,
  SiHeaderBrandDirective,
  SiHeaderSelectionItemComponent,
} from '@siemens/element-ng/application-header';
import {
  SiHeaderDropdownComponent,
  SiHeaderDropdownItemComponent,
  SiHeaderDropdownTriggerDirective,
} from '@siemens/element-ng/header-dropdown';

@Component({
  selector: 'app-root',
  imports: [
    RouterLink,
    RouterOutlet,
    SiApplicationHeaderComponent,
    SiHeaderActionsDirective,
    SiHeaderBrandDirective,
    SiHeaderDropdownComponent,
    SiHeaderDropdownItemComponent,
    SiHeaderDropdownTriggerDirective,
    SiHeaderSelectionItemComponent,
  ],
  templateUrl: './app.html',
})
export class App {
  protected readonly title = 'Staff & Skill Planning';
}
