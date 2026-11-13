import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import type { ImportRecord } from '../api/models';
import { IMPORT_STATUS } from './status';

export const SHOWN_ROW_ERRORS = 200;

@Component({
  selector: 'app-import-report',
  imports: [DatePipe, DecimalPipe, RouterLink, SiInlineNotificationComponent],
  templateUrl: './import-report.html',
  styleUrl: './import-report.scss',
})
export class ImportReport {
  readonly record = input.required<ImportRecord>();

  protected readonly status = computed(() => IMPORT_STATUS[this.record().status]);
  protected readonly summary = computed(() => {
    const { error, rows_succeeded, rows_total } = this.record();
    return error ?? `${rows_succeeded} of ${rows_total} rows imported.`;
  });
  protected readonly counts = computed(() => {
    const record = this.record();
    return [
      { label: 'Rows', value: record.rows_total },
      { label: 'Succeeded', value: record.rows_succeeded },
      { label: 'Failed', value: record.rows_failed },
      { label: 'Created', value: record.rows_created },
      { label: 'Updated', value: record.rows_updated },
      { label: 'Unchanged', value: record.rows_unchanged },
    ];
  });
  protected readonly shownErrors = computed(() =>
    this.record().row_errors.slice(0, SHOWN_ROW_ERRORS),
  );
}
