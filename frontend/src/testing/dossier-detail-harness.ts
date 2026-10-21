/** Test harness of the dossier page specs: the page with fake APIs for everything the sections load. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { DeferBlockBehavior, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { render, within } from '@testing-library/angular';
import { ToastService } from '@stupa-makers/ui-kit';
import { of } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { fakeApi, fakeAuth } from './event-fixtures';
import { ArchiveApi } from '../app/features/archive/api/archive-api.service';
import { AttachmentsApi } from '../app/features/dossiers/api/attachments-api.service';
import { ChecklistApi } from '../app/features/dossiers/api/checklist-api.service';
import { CommentsApi } from '../app/features/dossiers/api/comments-api.service';
import { DocumentsApi } from '../app/features/dossiers/api/documents-api.service';
import { EventsApi } from '../app/features/dossiers/api/events-api.service';
import { MailTemplatesApi } from '../app/features/dossiers/api/mail-templates-api.service';
import { DossierDetailComponent } from '../app/features/dossiers/detail/dossier-detail.component';

export const can = (...perms: string[]) => fakeAuth({ can: (p: string) => perms.includes(p) });

export interface SetupOptions {
  counts?: Record<string, number>;
  quotes?: unknown;
}

export async function setup(
  api = fakeApi(),
  auth = fakeAuth(),
  fakeTimers = false,
  opts: SetupOptions = {},
) {
  const view = await render(DossierDetailComponent, {
    inputs: { id: 'ev-1' },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      provideRouter([]),
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: EventsApi, useValue: api },
      { provide: AuthService, useValue: auth },
      {
        provide: AttachmentsApi,
        useValue: {
          counts: jest.fn(() =>
            of({
              attachments: 2,
              quotes: 1,
              howto: 1,
              openChecklist: 3,
              mailTemplates: 0,
              openComments: 4,
              ...opts.counts,
            }),
          ),
          list: jest.fn(() => of([])),
          quotes: jest.fn(() => of(opts.quotes ?? null)),
          retire: jest.fn(() => of(undefined)),
        },
      },
      {
        provide: DocumentsApi,
        useValue: { list: jest.fn(() => of([])), revisions: jest.fn(() => of([])), create: jest.fn() },
      },
      {
        provide: ChecklistApi,
        useValue: {
          get: jest.fn(() =>
            of({
              items: [],
              openRequired: { planning: 0, review: 0, live: 0, followup: 0 },
              template: null,
            }),
          ),
        },
      },
      {
        provide: MailTemplatesApi,
        useValue: { list: jest.fn(() => of([])), placeholders: jest.fn(() => of([])) },
      },
      { provide: CommentsApi, useValue: { list: jest.fn(() => of([])) } },
      { provide: ArchiveApi, useValue: { lastTime: jest.fn(() => of(null)), event: jest.fn() } },
      { provide: MediaApiService, useValue: { uploadImage: jest.fn() } },
    ],
  });
  view.fixture.detectChanges();
  if (fakeTimers) await jest.advanceTimersByTimeAsync(0);
  else await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toasts = () =>
    TestBed.inject(ToastService)
      .toasts()
      .map((t) => t.message);
  const page = view.fixture.componentInstance as unknown as {
    canLeave(): boolean | Promise<boolean>;
    useBudget(cents: number): void;
  };
  const router = TestBed.inject(Router);
  return {
    view,
    api,
    toasts,
    page,
    navigate: jest.spyOn(router, 'navigate').mockResolvedValue(true),
    http: TestBed.inject(HttpTestingController),
  };
}

export const indicator = (view: { container: Element }) =>
  within(view.container.querySelector('app-autosave-indicator') as HTMLElement).getByRole('status');
