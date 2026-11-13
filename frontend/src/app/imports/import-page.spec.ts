import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
  TestRequest,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { SiFileDropzoneComponent } from '@siemens/element-ng/file-uploader';
import { SiPaginationComponent } from '@siemens/element-ng/pagination';
import type { ImportPage as ImportHistory, ImportSummary } from '../api/models';
import { HISTORY_PAGE_SIZE, ImportPage } from './import-page';
import { partialImport } from './testing';

const summary: ImportSummary = { ...partialImport };

function history(items: ImportSummary[], total = items.length, page = 1): ImportHistory {
  return { items, total, page, page_size: HISTORY_PAGE_SIZE };
}

describe('ImportPage', () => {
  let fixture: ComponentFixture<ImportPage>;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ImportPage);
  });

  afterEach(() => http.verify());

  const view = () => fixture.nativeElement as HTMLElement;
  const dropzone = (): SiFileDropzoneComponent =>
    fixture.debugElement.query(By.directive(SiFileDropzoneComponent)).componentInstance;

  async function historyRequest(): Promise<TestRequest> {
    for (let attempt = 0; attempt < 20; attempt++) {
      TestBed.tick();
      const [request] = http.match((r) => r.url === '/api/v1/imports' && r.method === 'GET');
      if (request) {
        return request;
      }
      await new Promise((resolve) => setTimeout(resolve));
    }
    throw new Error('The import history was not requested');
  }

  /** Renders without awaiting stability, which would wait for the pending upload. */
  async function settle(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  }

  function drop(name = 'employees.csv'): File {
    const file = new File(['employee_number,first_name,last_name,email\n'], name);
    dropzone().filesAdded.emit([
      { file, fileName: name, status: 'added', size: '1 KB', progress: 0 },
    ]);
    return file;
  }

  it('lists past imports with their status', async () => {
    (await historyRequest()).flush(history([summary]));
    await fixture.whenStable();

    const cells = [...view().querySelectorAll('tbody td')].map((td) => td.textContent?.trim());
    expect(cells.slice(1)).toEqual(['employees-with-errors.csv', 'Partially succeeded', '2', '7']);
    expect(view().querySelector('tbody a')?.getAttribute('href')).toBe('/imports/3');
  });

  it('uploads a dropped file, shows the report and refreshes the history', async () => {
    (await historyRequest()).flush(history([]));
    await fixture.whenStable();
    expect(view().textContent).toContain('No imports yet.');

    const file = drop();
    await settle();
    expect(view().textContent).toContain('Importing employees.csv…');

    const upload = http.expectOne({ method: 'POST', url: '/api/v1/imports' });
    expect((upload.request.body as FormData).get('file')).toEqual(file);
    upload.flush(partialImport);
    await settle();

    expect(view().querySelector('app-import-report')?.textContent).toContain(
      '2 of 9 rows imported.',
    );
    (await historyRequest()).flush(history([summary]));
    await fixture.whenStable();
    expect(view().querySelector('tbody a')?.textContent).toBe('employees-with-errors.csv');
  });

  it('shows why the server rejected the upload', async () => {
    (await historyRequest()).flush(history([]));
    await fixture.whenStable();

    drop('huge.csv');
    await settle();
    http
      .expectOne({ method: 'POST', url: '/api/v1/imports' })
      .flush(
        { title: 'Content Too Large', status: 413, detail: 'The file is larger than 10 MB' },
        { status: 413, statusText: 'Content Too Large' },
      );
    await settle();

    expect(view().textContent).toContain('The file is larger than 10 MB');
    expect(view().querySelector('si-file-dropzone')).not.toBeNull();
  });

  it('reports files the dropzone refused without uploading them', async () => {
    (await historyRequest()).flush(history([]));
    await fixture.whenStable();

    dropzone().filesAdded.emit([
      {
        file: new File(['x'], 'photo.png'),
        fileName: 'photo.png',
        status: 'invalid',
        size: '1 KB',
        progress: 0,
      },
    ]);
    dropzone().fileError.emit({
      file: new File(['x'], 'photo.png'),
      fileName: 'photo.png',
      status: 'invalid',
      size: '1 KB',
      progress: 0,
      errorText: 'Incorrect file type selected',
    });
    await settle();

    expect(view().textContent).toContain('Incorrect file type selected');
    http.expectNone({ method: 'POST', url: '/api/v1/imports' });
  });

  it('pages through a long history', async () => {
    (await historyRequest()).flush(history([summary], 25));
    await fixture.whenStable();

    const paginator: SiPaginationComponent = fixture.debugElement.query(
      By.directive(SiPaginationComponent),
    ).componentInstance;
    paginator.currentPage.set(2);
    await settle();

    const request = await historyRequest();
    expect(request.request.params.get('page')).toBe('2');
    request.flush(history([summary], 25, 2));
  });

  it('shows when the history cannot be loaded', async () => {
    (await historyRequest()).flush(null, { status: 0, statusText: 'Unknown Error' });
    await fixture.whenStable();

    expect(view().textContent).toContain('The server cannot be reached.');
  });
});
