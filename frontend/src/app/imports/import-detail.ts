import { httpResource } from '@angular/common/http';
import { Component, computed, input, numberAttribute } from '@angular/core';
import { SiBreadcrumbComponent } from '@siemens/element-ng/breadcrumb';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import type { ImportRecord } from '../api/models';
import { problemMessage } from '../api/problem';
import { ImportReport } from './import-report';

@Component({
  selector: 'app-import-detail',
  imports: [
    ImportReport,
    SiBreadcrumbComponent,
    SiInlineNotificationComponent,
    SiLoadingSpinnerComponent,
  ],
  host: { class: 'd-block container-fluid py-6' },
  template: `
    <si-breadcrumb
      showRootAsText
      class="d-block mb-4"
      [items]="[
        { title: 'Find people', link: '/employees' },
        { title: 'Import employees', link: '/imports' },
        { title: 'Import report' },
      ]"
    />
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
