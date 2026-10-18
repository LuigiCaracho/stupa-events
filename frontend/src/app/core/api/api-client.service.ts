/** Typed access to the shell endpoints; wire names are normalized to the camelCase models. */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { type Observable, map } from 'rxjs';
import { API_BASE_URL } from './api.config';
import type { LogoutResult, Principal } from './models';

type Wire = Record<string, unknown>;

const pick = <T>(wire: Wire, camel: string, snake: string, fallback: T): T =>
  (wire[camel] ?? wire[snake] ?? fallback) as T;

/** Accepts camelCase (contract) and snake_case (upstream copy) so the shell survives either. */
export function toPrincipal(wire: Wire): Principal {
  return {
    sub: String(wire['sub']),
    email: pick(wire, 'email', 'email', null),
    displayName: pick(wire, 'displayName', 'display_name', null),
    roles: pick(wire, 'roles', 'roles', []),
    permissions: pick(wire, 'permissions', 'permissions', []),
    groups: pick(wire, 'groups', 'groups', []),
    organizations: pick(wire, 'organizations', 'organizations', []),
  };
}

@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  me(): Observable<Principal> {
    return this.http.get<Wire>(`${this.base}/auth/me`).pipe(map(toPrincipal));
  }

  logout(): Observable<LogoutResult> {
    return this.http
      .post<Wire>(`${this.base}/auth/logout`, {})
      .pipe(map((w) => ({ logoutUrl: pick<string | null>(w, 'logoutUrl', 'logout_url', null) })));
  }
}
