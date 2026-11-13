import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { ImportDetail } from './import-detail';
import { partialImport } from './testing';

describe('ImportDetail', () => {
  let harness: RouterTestingHarness;
  let http: HttpTestingController;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter(
          [{ path: 'imports/:id', component: ImportDetail }],
          withComponentInputBinding(),
        ),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    harness = await RouterTestingHarness.create();
  });

  afterEach(() => http.verify());

  async function open(id: number) {
    await harness.navigateByUrl(`/imports/${id}`);
    TestBed.tick();
    return http.expectOne(`/api/v1/imports/${id}`);
  }

  it('shows the report of the import in the URL', async () => {
    (await open(3)).flush(partialImport);
    await harness.fixture.whenStable();

    expect(harness.routeNativeElement?.textContent).toContain('employees-with-errors.csv');
    expect(harness.routeNativeElement?.textContent).toContain('2 of 9 rows imported.');
  });

  it('shows the problem when the import does not exist', async () => {
    (await open(999)).flush(
      { title: 'Not Found', status: 404, detail: 'Import 999 does not exist' },
      { status: 404, statusText: 'Not Found' },
    );
    await harness.fixture.whenStable();

    expect(harness.routeNativeElement?.textContent).toContain('Import 999 does not exist');
  });
});
