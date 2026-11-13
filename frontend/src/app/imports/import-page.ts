import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient, httpResource } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SiBadgeComponent } from '@siemens/element-ng/badge';
import { SiFileDropzoneComponent } from '@siemens/element-ng/file-uploader';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import { SiPaginationComponent } from '@siemens/element-ng/pagination';
import { firstValueFrom } from 'rxjs';
import type { ImportPage as ImportHistory, ImportRecord } from '../api/models';
import { problemMessage } from '../api/problem';
import { ImportReport } from './import-report';
import { IMPORT_STATUS } from './status';

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const HISTORY_PAGE_SIZE = 10;

interface DroppedFile {
  file: File;
  status: string;
}

@Component({
  selector: 'app-import-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ImportReport,
    RouterLink,
    SiBadgeComponent,
    SiFileDropzoneComponent,
    SiInlineNotificationComponent,
    SiLoadingSpinnerComponent,
    SiPaginationComponent,
  ],
  templateUrl: './import-page.html',
})
export class ImportPage {
  private readonly http = inject(HttpClient);

  protected readonly maxUploadBytes = MAX_UPLOAD_BYTES;
  protected readonly historyPageSize = HISTORY_PAGE_SIZE;
  protected readonly importStatus = IMPORT_STATUS;

  protected readonly uploading = signal<string | undefined>(undefined);
  protected readonly result = signal<ImportRecord | undefined>(undefined);
  protected readonly uploadError = signal<string | undefined>(undefined);

  protected readonly historyPage = signal(1);
  protected readonly history = httpResource<ImportHistory>(() => ({
    url: '/api/v1/imports',
    params: { page: this.historyPage(), page_size: HISTORY_PAGE_SIZE },
  }));
  protected readonly historyError = computed(() => {
    const error = this.history.error();
    return error ? problemMessage(error) : undefined;
  });

  protected async upload(files: DroppedFile[]): Promise<void> {
    const file = files.find((dropped) => dropped.status === 'added')?.file;
    if (!file) {
      return;
    }
    const body = new FormData();
    body.append('file', file, file.name);
    this.uploading.set(file.name);
    this.uploadError.set(undefined);
    this.result.set(undefined);
    try {
      this.result.set(await firstValueFrom(this.http.post<ImportRecord>('/api/v1/imports', body)));
      this.historyPage.set(1);
      this.history.reload();
    } catch (error) {
      this.uploadError.set(problemMessage(error));
    } finally {
      this.uploading.set(undefined);
    }
  }

  protected rejectFile(error: { errorText: string }): void {
    this.result.set(undefined);
    this.uploadError.set(error.errorText);
  }
}
