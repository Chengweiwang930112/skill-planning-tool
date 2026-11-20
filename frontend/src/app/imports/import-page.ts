import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient, HttpEventType, HttpResponse, httpResource } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SiBreadcrumbComponent } from '@siemens/element-ng/breadcrumb';
import { SiBadgeComponent } from '@siemens/element-ng/badge';
import { SiFileDropzoneComponent } from '@siemens/element-ng/file-uploader';
import { SiInlineNotificationComponent } from '@siemens/element-ng/inline-notification';
import { SiLoadingSpinnerComponent } from '@siemens/element-ng/loading-spinner';
import { SiPaginationComponent } from '@siemens/element-ng/pagination';
import { SiProgressbarComponent } from '@siemens/element-ng/progressbar';
import { filter, lastValueFrom, tap } from 'rxjs';
import type { ImportPage as ImportHistory, ImportRecord } from '../api/models';
import { problemMessage } from '../api/problem';
import { ImportReport } from './import-report';
import { IMPORT_STATUS } from './status';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const HISTORY_PAGE_SIZE = 10;

interface DroppedFile {
  file: File;
  status: string;
}

/** A file on its way: uploaded while `sent` is short of `size`, then imported. */
interface Upload {
  name: string;
  sent: number;
  size: number;
}

@Component({
  selector: 'app-import-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ImportReport,
    RouterLink,
    SiBreadcrumbComponent,
    SiBadgeComponent,
    SiFileDropzoneComponent,
    SiInlineNotificationComponent,
    SiLoadingSpinnerComponent,
    SiPaginationComponent,
    SiProgressbarComponent,
  ],
  host: { class: 'd-block container-fluid py-6' },
  templateUrl: './import-page.html',
})
export class ImportPage {
  private readonly http = inject(HttpClient);

  protected readonly maxUploadBytes = MAX_UPLOAD_BYTES;
  protected readonly historyPageSize = HISTORY_PAGE_SIZE;
  protected readonly importStatus = IMPORT_STATUS;

  protected readonly uploading = signal<Upload | undefined>(undefined);
  protected readonly percent = computed(() => {
    const upload = this.uploading();
    return upload ? Math.floor((100 * upload.sent) / Math.max(upload.size, 1)) : 0;
  });
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
    this.uploading.set({ name: file.name, sent: 0, size: file.size });
    this.uploadError.set(undefined);
    this.result.set(undefined);
    try {
      const events = this.http.post<ImportRecord>('/api/v1/imports', body, {
        reportProgress: true,
        observe: 'events',
      });
      const response = await lastValueFrom(
        events.pipe(
          tap((event) => {
            if (event.type === HttpEventType.UploadProgress) {
              const size = event.total ?? file.size;
              this.uploading.set({ name: file.name, sent: Math.min(event.loaded, size), size });
            }
          }),
          filter((event) => event instanceof HttpResponse),
        ),
      );
      this.result.set(response.body!);
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
