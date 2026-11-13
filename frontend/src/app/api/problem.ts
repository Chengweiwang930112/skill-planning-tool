import { HttpErrorResponse } from '@angular/common/http';
import type { ProblemDetail } from './models';

export function problemMessage(error: unknown): string {
  if (!(error instanceof HttpErrorResponse)) {
    return 'Something went wrong.';
  }
  if (error.status === 0) {
    return 'The server cannot be reached.';
  }
  const problem = error.error as Partial<ProblemDetail> | null;
  return problem?.detail ?? problem?.title ?? error.message;
}
