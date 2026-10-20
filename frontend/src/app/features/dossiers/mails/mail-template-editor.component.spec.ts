import { HttpErrorResponse } from '@angular/common/http';
import type { Provider } from '@angular/core';
import { DeferBlockBehavior } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { createLocationMock, provideLocationMock } from '../../../../testing/location-mock';
import { DocumentsApi } from '../api/documents-api.service';
import { MailTemplatesApi } from '../api/mail-templates-api.service';
import type { MailTemplateOut } from '../model/document.models';
import { MailTemplateEditorComponent } from './mail-template-editor.component';

const template: MailTemplateOut = {
  id: 'm1',
  title: 'Einladung',
  subject: 'Einladung zu {{ event.title }}',
  visibility: 'org',
  rev: 2,
  updatedAt: '',
  bodyMd: 'Hallo {{ org.name }}',
  meta: {},
};
const placeholders = [
  { path: 'event.title', label: 'Titel', example: 'Movienight' },
  { path: 'org.name', label: 'Organisation', example: 'FSI' },
];

function fakeApi(over: Record<string, unknown> = {}) {
  return {
    preview: jest.fn(() => of({ subject: 'Einladung zu Movienight', body: 'Hallo FSI' })),
    put: jest.fn(() => of(template)),
    ...over,
  };
}

async function setup(
  api = fakeApi(),
  inputs: Record<string, unknown> = {},
  extra: { providers?: Provider[] } = {},
) {
  const saved = jest.fn();
  const view = await render(MailTemplateEditorComponent, {
    inputs: { eventId: 'e1', template, placeholders, canEdit: true, ...inputs },
    on: { saved },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      ...(extra.providers ?? []),
      { provide: MailTemplatesApi, useValue: api },
      { provide: DocumentsApi, useValue: { putDraft: jest.fn(() => of({})) } },
      { provide: MediaApiService, useValue: {} },
    ],
  });
  await jest.advanceTimersByTimeAsync(500);
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return { ...view, api, saved, success: jest.spyOn(toast, 'success'), toast };
}

describe('MailTemplateEditorComponent', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('renders the preview of the stored template', async () => {
    const { api } = await setup();
    expect(api.preview).toHaveBeenCalledWith('e1', 'm1', {
      subject: 'Einladung zu {{ event.title }}',
      bodyMd: 'Hallo {{ org.name }}',
    });
    expect(screen.getByText('Einladung zu Movienight')).toBeInTheDocument();
    expect(screen.getByText('Hallo FSI')).toBeInTheDocument();
  });

  it('inserts a placeholder from its chip at the cursor and previews again', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('button', { name: '{{ event.title }}' }), {
      advanceTimers: jest.advanceTimersByTime,
    });
    await jest.advanceTimersByTimeAsync(500);
    expect(api.preview).toHaveBeenLastCalledWith(
      'e1',
      'm1',
      expect.objectContaining({ bodyMd: expect.stringContaining('{{ event.title }}') }),
    );
  });

  it('shows the findings of a refused template with the allowed placeholders', async () => {
    const api = fakeApi({
      preview: jest.fn(() =>
        throwError(
          () =>
            new HttpErrorResponse({
              status: 422,
              error: {
                status: 422,
                code: 'template_invalid',
                reasons: [
                  {
                    code: 'unknown_placeholder',
                    field: 'event.raum',
                    allowed: ['event.title'],
                    severity: 'blocker',
                    messageKey: '',
                    fixAction: null,
                  },
                ],
              },
            }),
        ),
      ),
    });
    await setup(api);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Unbekannter Platzhalter {{ event.raum }}. Erlaubt sind: {{ event.title }}',
    );
  });

  it('shows another failure as a generic sentence', async () => {
    await setup(
      fakeApi({ preview: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }),
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('copies the rendered text, with a hint when copying is blocked', async () => {
    const writeText = jest.fn(() => Promise.resolve());
    Object.assign(navigator, { clipboard: { writeText } });
    const { success, toast } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Text kopieren' }), {
      advanceTimers: jest.advanceTimersByTime,
    });
    expect(writeText).toHaveBeenCalledWith('Einladung zu Movienight\n\nHallo FSI');
    expect(success).toHaveBeenCalledWith('Text kopiert.');
    Object.assign(navigator, { clipboard: undefined });
    const show = jest.spyOn(toast, 'show');
    await userEvent.click(screen.getByRole('button', { name: 'Text kopieren' }), {
      advanceTimers: jest.advanceTimersByTime,
    });
    expect(show).toHaveBeenCalled();
  });

  it('warns instead of opening a mail that is too long', async () => {
    const api = fakeApi({ preview: jest.fn(() => of({ subject: 's', body: 'x'.repeat(2000) })) });
    await setup(api);
    await userEvent.click(screen.getByRole('button', { name: 'Als Mail öffnen' }), {
      advanceTimers: jest.advanceTimersByTime,
    });
    expect(screen.getByText('Text zu lang für den Mailknopf, bitte kopieren.')).toBeInTheDocument();
  });

  it('opens a short mail through mailto', async () => {
    const location = createLocationMock();
    await setup(fakeApi(), {}, { providers: [provideLocationMock(location)] });
    await userEvent.click(screen.getByRole('button', { name: 'Als Mail öffnen' }), {
      advanceTimers: jest.advanceTimersByTime,
    });
    expect(location.assign).toHaveBeenCalledWith(expect.stringMatching(/^mailto:\?subject=/));
  });

  it('saves with the revision and reports the stored template', async () => {
    const { api, saved, success } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Vorlage speichern' }), {
      advanceTimers: jest.advanceTimersByTime,
    });
    expect(api.put).toHaveBeenCalledWith(
      'e1',
      'm1',
      2,
      expect.objectContaining({ subject: 'Einladung zu {{ event.title }}', title: 'Einladung' }),
    );
    expect(saved).toHaveBeenCalledWith(template);
    expect(success).toHaveBeenCalledWith('Vorlage gespeichert.');
  });

  it('creates a new template and shows a refusal on save', async () => {
    const put = jest.fn(() =>
      throwError(
        () =>
          new HttpErrorResponse({ status: 422, error: { status: 422, code: 'subject_newline' } }),
      ),
    );
    const { api } = await setup(fakeApi({ put }), { template: null });
    const subject = screen.getByLabelText('Betreff');
    await userEvent.type(subject, 'Neu', { advanceTimers: jest.advanceTimersByTime });
    await userEvent.click(screen.getByRole('button', { name: 'Vorlage speichern' }), {
      advanceTimers: jest.advanceTimersByTime,
    });
    expect(api.put).toHaveBeenCalledWith(
      'e1',
      'new',
      0,
      expect.objectContaining({ subject: 'Neu', title: 'Neu' }),
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Zeilenumbruch');
  });

  it('is read-only for a reader', async () => {
    await setup(fakeApi(), { canEdit: false });
    expect(screen.queryByRole('button', { name: 'Vorlage speichern' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '{{ event.title }}' })).toBeDisabled();
  });
});
