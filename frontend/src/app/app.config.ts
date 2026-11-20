import { provideHttpClient, withXhr } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // XHR rather than the default fetch, which cannot report how far an upload is.
    provideHttpClient(withXhr()),
    provideRouter(routes, withComponentInputBinding()),
  ],
};
