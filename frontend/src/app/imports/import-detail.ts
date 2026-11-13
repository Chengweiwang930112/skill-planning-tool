import { httpResource } from '@angular/common/http';
import { Component, computed, input, numberAttribute } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import type { ImportRecord } from '../api/models';
import { problemMessage } from '../api/problem';
import { ImportReport } from './import-report';

@Component({
  selector: 'app-import-detail',
  imports: [ImportReport, RouterLink, SiInlineNotificationComponent, SiLoadingSpinnerComponent],
  template: `
    <a class="d-inline-block mb-4" routerLink="/imports">← All imports</a>
    @if (error(); as message) {
      <si-inline-notification
        severity="danger"
        heading="The import could not be loaded."
        [message]="message"
      />
    } @else if (record.value(); as value) {
      <app-import-report [record]="value" />
    } @else {
      <si-loading-spinner />
    }
  `,
})
export class ImportDetail {
  readonly id = input.required({ transform: numberAttribute });

  protected readonly record = httpResource<ImportRecord>(() => `/api/v1/imports/${this.id()}`);
  protected readonly error = computed(() => {
    const error = this.record.error();
    return error ? problemMessage(error) : undefined;
  });
}
