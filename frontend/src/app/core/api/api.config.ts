/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/api/api.config.ts (mock switch removed). */
import { InjectionToken } from '@angular/core';

/** Base path of the REST API (`web` nginx routes `/api` to `api`). */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  providedIn: 'root',
  factory: () => '/api',
});
