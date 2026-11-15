import { HttpErrorResponse } from '@angular/common/http';
import { problemMessage } from './problem';

describe('problemMessage', () => {
  it('prefers the problem detail', () => {
    // Given
    const error = new HttpErrorResponse({
      status: 404,
      error: { title: 'Not Found', status: 404, detail: 'Employee 7 does not exist' },
    });

    // When / Then
    expect(problemMessage(error)).toBe('Employee 7 does not exist');
  });

  it('falls back to the title, then the HTTP message', () => {
    // Given
    const titled = new HttpErrorResponse({
      status: 500,
      error: { title: 'Internal Server Error' },
    });
    const bare = new HttpErrorResponse({ status: 502, statusText: 'Bad Gateway', url: '/api' });

    // When / Then
    expect(problemMessage(titled)).toBe('Internal Server Error');
    expect(problemMessage(bare)).toContain('502 Bad Gateway');
  });

  it('explains when the server is unreachable', () => {
    // When / Then
    expect(problemMessage(new HttpErrorResponse({ status: 0 }))).toBe(
      'The server cannot be reached.',
    );
  });

  it('handles errors that are not HTTP errors', () => {
    // When / Then
    expect(problemMessage(new Error('boom'))).toBe('Something went wrong.');
  });
});
