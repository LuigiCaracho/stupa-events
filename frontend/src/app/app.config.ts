/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/app.config.ts (rewritten) */
/**
 * Application providers. Rewritten from the workflow tool:
 * no mock API, no live-vote or branding services. The interceptor order is loading
 * (outermost, measures the full duration), cache, auth (credentials and CSRF header).
 */
import {
  type ApplicationConfig,
  inject,
  isDevMode,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';
import { provideServiceWorker } from '@angular/service-worker';
import { UI_KIT_INTL, UI_KIT_LOADING, uiKitIntlFromLang } from '@stupa-makers/ui-kit';
import { authInterceptor } from '@core/auth/auth.interceptor';
import { AuthService } from '@core/auth/auth.service';
import { cacheInterceptor } from '@core/cache/cache.interceptor';
import { I18nService } from '@core/i18n/i18n.service';
import { loadingInterceptor } from '@core/loading/loading.interceptor';
import { LoadingService } from '@core/loading/loading.service';
import { SwUpdateService } from '@core/pwa/sw-update.service';
import { ThemeService } from '@core/theme/theme.service';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled', anchorScrolling: 'enabled' }),
    ),
    provideHttpClient(withInterceptors([loadingInterceptor, cacheInterceptor, authInterceptor])),
    { provide: UI_KIT_INTL, useFactory: () => uiKitIntlFromLang(inject(I18nService).locale) },
    { provide: UI_KIT_LOADING, useFactory: () => ({ visible: inject(LoadingService).visible }) },
    provideAppInitializer(() => {
      inject(ThemeService).init();
      const i18n = inject(I18nService);
      inject(AuthService).ensureLoaded().subscribe();
      inject(SwUpdateService).init();
      return i18n.ready();
    }),
    // ngsw-config.json caches the app shell and the assets. It does not cache /api.
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000',
    }),
  ],
};
