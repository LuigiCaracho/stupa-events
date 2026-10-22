/** Mounts a public page at its route with a fake HTTP backend, so a spec can answer the calls the page makes. */
import type { Type } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

export interface PublicHarness<T> {
  harness: RouterTestingHarness;
  component: T;
  http: HttpTestingController;
  router: Router;
}

export async function mountPublic<T>(
  page: Type<T>,
  path: string,
  url: string,
): Promise<PublicHarness<T>> {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([{ path, component: page }], withComponentInputBinding()),
      provideHttpClient(),
      provideHttpClientTesting(),
    ],
  });
  const harness = await RouterTestingHarness.create();
  const component = await harness.navigateByUrl(url, page);
  return {
    harness,
    component,
    http: TestBed.inject(HttpTestingController),
    router: TestBed.inject(Router),
  };
}

/** Lets pending promises and timers run and renders the page. */
export async function tick(h: { harness: RouterTestingHarness }): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  h.harness.detectChanges();
}

/** Answers the calls of the page: `answers` maps a URL to a body or `{ status, body }` for a failure. */
export async function answer(
  h: PublicHarness<unknown>,
  answers: Record<string, object | { status: number; body: object }>,
): Promise<void> {
  h.harness.detectChanges();
  for (const [url, value] of Object.entries(answers)) {
    const req = h.http.expectOne((r) => r.url === url);
    const failure = value as { status?: number; body?: object };
    if (typeof failure?.status === 'number' && 'body' in failure) {
      req.flush(failure.body ?? null, { status: failure.status, statusText: 'x' });
    } else {
      req.flush(value);
    }
  }
  await tick(h);
  await tick(h);
}
