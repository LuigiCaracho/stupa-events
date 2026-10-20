import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import { DocumentsApi } from '../api/documents-api.service';
import { MailTemplatesApi } from '../api/mail-templates-api.service';
import { MailsTabComponent } from './mails-tab.component';

const summary = {
  id: 'm1',
  title: 'Einladung',
  subject: 'Hallo',
  visibility: 'org',
  rev: 1,
  updatedAt: '',
};
const full = { ...summary, bodyMd: 'Text', meta: {} };

function fakeApi(over: Record<string, unknown> = {}) {
  return {
    list: jest.fn(() => of([summary])),
    get: jest.fn(() => of(full)),
    placeholders: jest.fn(() => of([{ path: 'event.title', label: 'Titel', example: 'X' }])),
    preview: jest.fn(() => of({ subject: 'Hallo', body: 'Text' })),
    put: jest.fn(() => of(full)),
    ...over,
  };
}

async function setup(api = fakeApi(), inputs: Record<string, unknown> = {}) {
  const changed = jest.fn();
  const view = await render(MailsTabComponent, {
    inputs: { event: makeEvent({}), canEdit: true, ...inputs },
    on: { changed },
    providers: [
      { provide: MailTemplatesApi, useValue: api },
      { provide: DocumentsApi, useValue: { putDraft: jest.fn(() => of({})) } },
      { provide: MediaApiService, useValue: {} },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { ...view, api, changed };
}

describe('MailsTabComponent', () => {
  it('lists the templates and says that nothing is sent from the dossier', async () => {
    await setup();
    expect(screen.getByText(/nie versendet/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Einladung/ })).toBeInTheDocument();
    expect(screen.getByText('Wähle eine Vorlage aus der Liste.')).toBeInTheDocument();
  });

  it('opens a template in the editor', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('button', { name: /Einladung/ }));
    expect(api.get).toHaveBeenCalledWith('ev-1', 'm1');
    expect(await screen.findByLabelText('Betreff')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Einladung/ })).toHaveAttribute(
      'aria-current',
      'true',
    );
  });

  it('starts a new template, and refreshes the list after saving', async () => {
    const { api, changed } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Neue Vorlage' }));
    await userEvent.type(await screen.findByLabelText('Betreff'), 'Neu');
    await userEvent.click(screen.getByRole('button', { name: 'Vorlage speichern' }));
    expect(api.put).toHaveBeenCalled();
    expect(api.list).toHaveBeenCalledTimes(2);
    expect(changed).toHaveBeenCalled();
  });

  it('shows the empty state and the error note', async () => {
    await setup(fakeApi({ list: jest.fn(() => of([])) }), { canEdit: false });
    expect(screen.getByText('Noch keine Mailvorlagen.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Neue Vorlage' })).not.toBeInTheDocument();
  });

  it('shows an error note when the list fails and survives missing placeholders', async () => {
    await setup(
      fakeApi({
        list: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
        placeholders: jest.fn(() => throwError(() => new Error('x'))),
      }),
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Mailvorlagen konnten nicht geladen werden.',
    );
  });
});
