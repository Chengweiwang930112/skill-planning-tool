import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import type { ImportRecord } from '../api/models';
import { ImportReport, SHOWN_ROW_ERRORS } from './import-report';
import { partialImport } from './testing';

async function render(record: ImportRecord): Promise<HTMLElement> {
  TestBed.configureTestingModule({ providers: [provideRouter([])] });
  const fixture = TestBed.createComponent(ImportReport);
  fixture.componentRef.setInput('record', record);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('ImportReport', () => {
  it('summarises the counts and lists the row errors', async () => {
    const view = await render(partialImport);

    expect(view.querySelector('si-inline-notification')?.textContent).toContain(
      '2 of 9 rows imported.',
    );
    const counts = [...view.querySelectorAll('.counts div')].map(
      (d) => `${d.querySelector('dt')?.textContent} ${d.querySelector('dd')?.textContent}`,
    );
    expect(counts).toEqual([
      'Rows 9',
      'Succeeded 2',
      'Failed 7',
      'Created 2',
      'Updated 0',
      'Unchanged 0',
    ]);
    const rows = [...view.querySelectorAll('tbody tr')].map((tr) =>
      [...tr.querySelectorAll('td')].map((td) => td.textContent?.trim()),
    );
    expect(rows).toEqual([
      ['3', 'first_name', 'is required'],
      ['9', '—', 'Expected 8 values, found 9'],
    ]);
    expect(view.querySelector('a[href="/employees"]')).not.toBeNull();
  });

  it('explains why a whole file was rejected and offers no link to employees', async () => {
    const view = await render({
      ...partialImport,
      status: 'failed',
      rows_total: 0,
      rows_succeeded: 0,
      rows_failed: 0,
      rows_created: 0,
      error: 'Missing required columns: email',
      row_errors: [],
    });

    expect(view.textContent).toContain('Missing required columns: email');
    expect(view.querySelector('table')).toBeNull();
    expect(view.querySelector('a[href="/employees"]')).toBeNull();
  });

  it('shows only the first errors of a file with very many', async () => {
    const row_errors = Array.from({ length: SHOWN_ROW_ERRORS + 50 }, (_, i) => ({
      row: i + 2,
      field: 'email',
      message: 'value is not a valid email address',
    }));

    const view = await render({ ...partialImport, row_errors });

    expect(view.querySelectorAll('tbody tr')).toHaveLength(SHOWN_ROW_ERRORS);
    expect(view.textContent).toContain('Showing the first 200 of 250 errors.');
  });
});
