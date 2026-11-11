import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import {
  SiApplicationHeaderComponent,
  SiHeaderAccountItemComponent,
  SiHeaderActionsDirective,
  SiHeaderBrandDirective,
  SiHeaderLogoDirective,
} from '@siemens/element-ng/application-header';
import { BadgeType, SiBadgeComponent } from '@siemens/element-ng/badge';
import { SiCardComponent } from '@siemens/element-ng/card';
import { SiEmptyStateComponent } from '@siemens/element-ng/empty-state';
import {
  SiHeaderDropdownComponent,
  SiHeaderDropdownItemComponent,
  SiHeaderDropdownTriggerDirective,
} from '@siemens/element-ng/header-dropdown';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { ButtonShowcase } from './button-showcase/button-showcase';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    SiApplicationHeaderComponent,
    SiHeaderBrandDirective,
    SiHeaderLogoDirective,
    SiHeaderActionsDirective,
    SiHeaderAccountItemComponent,
    SiHeaderDropdownComponent,
    SiHeaderDropdownItemComponent,
    SiHeaderDropdownTriggerDirective,
    SiInlineNotificationComponent,
    SiCardComponent,
    SiEmptyStateComponent,
    SiBadgeComponent,
    ButtonShowcase,
  ],
  templateUrl: './app.html',
})
export class App {
  protected readonly title = 'Staff & Skill Planning Tool';

  protected readonly proficiencyLevels: { label: string; badge: BadgeType }[] = [
    { label: 'Beginner', badge: 'default' },
    { label: 'Intermediate', badge: 'info' },
    { label: 'Advanced', badge: 'success' },
    { label: 'Expert', badge: 'success-emphasis' },
  ];
}
