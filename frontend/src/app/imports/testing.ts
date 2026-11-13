import type { ImportRecord } from '../api/models';

export const partialImport: ImportRecord = {
  id: 3,
  filename: 'employees-with-errors.csv',
  status: 'partially_succeeded',
  rows_total: 9,
  rows_succeeded: 2,
  rows_failed: 7,
  rows_created: 2,
  rows_updated: 0,
  rows_unchanged: 0,
  error: null,
  file_sha256: 'c0a7df61f764',
  created_at: '2026-11-13T09:30:00Z',
  row_errors: [
    { row: 3, field: 'first_name', message: 'is required' },
    { row: 9, field: null, message: 'Expected 8 values, found 9' },
  ],
};
