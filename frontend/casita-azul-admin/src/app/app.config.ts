import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { provideClientHydration } from '@angular/platform-browser';

import { authInterceptor } from './interceptors/auth-interceptor'; // CORRECTED PATH: Check if './interceptors/' exists

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideClientHydration(),
    // Register the interceptor
    provideHttpClient(withFetch(), withInterceptors([authInterceptor])),
  ]
};