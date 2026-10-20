import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { AuthService } from '@core/auth/auth.service';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import { ChecklistApi } from '../api/checklist-api.service';
import type { ChecklistItemOut, ChecklistOut } from '../model/checklist.models';
import { ChecklistTabComponent } from './checklist-tab.component';

const item = (o: Partial<ChecklistItemOut>): ChecklistItemOut => ({
  id: 'c1',
  text: 'Raum buchen',
  phase: 'planning',
  required: true,
  position: 1,
  assigneeSub: null,
  assigneeName: null,
  dueAt: null,
  dueOffsetDays: null,
  dueManual: false,
  overdue: false,
  doneAt: null,
  doneBy: null,
  waivedReason: null,
  fromTemplate: false,
  ...o,
});

const list = (items: ChecklistItemOut[]): ChecklistOut => ({
  items,
  openRequired: { planning: 1, review: 0, live: 0, followup: 0 },
  template: { slug: 'movie', name: 'Movienight' },
});

function fakeApi(
  items = [
    item({}),
    item({
      id: 'c2',
      text: 'Nachbereitung',
      phase: 'followup',
      position: 2,
      required: false,
      assigneeSub: 'me',
      assigneeName: 'Ich',
    }),
  ],
) {
  return {
    get: jest.fn(() => of(list(items))),
    applyTemplate: jest.fn(() => of({ ...list(items), added: 3 })),
    add: jest.fn(() => of(item({}))),
    patch: jest.fn(() => of(item({}))),
    done: jest.fn(() => of(item({}))),
    remove: jest.fn(() => of(undefined)),
  };
}

async function setup(api = fakeApi(), inputs: Record<string, unknown> = {}) {
  const changed = jest.fn();
  const view = await render(ChecklistTabComponent, {
    inputs: { event: makeEvent({}), canEdit: true, ...inputs },
    on: { changed },
    providers: [
      { provide: ChecklistApi, useValue: api },
      { provide: AuthService, useValue: { userId: () => 'me', displayName: () => 'Ich' } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return {
    ...view,
    api,
    changed,
    success: jest.spyOn(toast, 'success'),
    error: jest.spyOn(toast, 'error'),
  };
}

describe('ChecklistTabComponent', () => {
  it('groups by phase and counts open required points', async () => {
    await setup();
    expect(screen.getByRole('heading', { name: /Planung/ })).toHaveTextContent(
      '1 Pflichtpunkte offen',
    );
    expect(screen.getByRole('heading', { name: 'Nachbereitung' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Freigabe' })).not.toBeInTheDocument();
    expect(screen.getByText('Vorlage: Movienight')).toBeInTheDocument();
  });

  it('shows an empty state and an error note', async () => {
    await setup(fakeApi([]));
    expect(screen.getByText('Noch keine Punkte.')).toBeInTheDocument();
  });

  it('shows an error note when loading fails', async () => {
    const api = {
      ...fakeApi(),
      get: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
    };
    await setup(api);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Checkliste konnte nicht geladen werden.',
    );
  });

  it('applies the template and reports how many points came in', async () => {
    const { api, success, changed } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Vorlage anwenden' }));
    expect(api.applyTemplate).toHaveBeenCalledWith('ev-1');
    expect(success).toHaveBeenCalledWith('3 Punkte aus der Vorlage hinzugefügt.');
    expect(changed).toHaveBeenCalled();
  });

  it('ticks the own point without the edit right', async () => {
    const { api, fixture } = await setup(fakeApi(), { canEdit: false });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(screen.getByRole('checkbox', { name: /Raum buchen/ })).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: /Nachbereitung/ }));
    expect(api.done).toHaveBeenCalledWith('c2', true);
    expect(screen.queryByRole('button', { name: 'Vorlage anwenden' })).not.toBeInTheDocument();
  });

  it('adds an own point and validates the text', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Punkt hinzufügen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Punkt anlegen' }));
    expect(screen.getByText('Bitte den Punkt beschreiben.')).toBeInTheDocument();
    await userEvent.type(screen.getByRole('textbox'), 'Schlüssel holen');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Pflichtpunkt' }));
    await userEvent.click(screen.getByRole('button', { name: 'Punkt anlegen' }));
    expect(api.add).toHaveBeenCalledWith('ev-1', {
      text: 'Schlüssel holen',
      phase: 'planning',
      required: true,
    });
    expect(screen.queryByRole('button', { name: 'Punkt anlegen' })).not.toBeInTheDocument();
  });

  it('can close the add form', async () => {
    await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Punkt hinzufügen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(screen.getByRole('button', { name: 'Punkt hinzufügen' })).toBeInTheDocument();
  });

  it('sends assign, waive and delete commands and shows server refusals', async () => {
    const api = fakeApi();
    api.patch.mockReturnValueOnce(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 422,
            error: { status: 422, code: 'waiver_reason_required' },
          }),
      ) as never,
    );
    const { error } = await setup(api);
    await userEvent.click(screen.getAllByRole('button', { name: 'Aktionen für den Punkt' })[0]);
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Entfällt mit Grund' }));
    await userEvent.type(screen.getByLabelText('Grund'), 'ist leider nicht mehr nötig');
    await userEvent.click(screen.getByRole('button', { name: 'Entfällt' }));
    expect(error).toHaveBeenCalledWith('Ein Pflichtpunkt kann nur mit Grund entfallen.');
    await userEvent.click(screen.getAllByRole('button', { name: 'Aktionen für den Punkt' })[0]);
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Zuweisen' }));
    await userEvent.click(screen.getByRole('combobox'));
    await userEvent.click(await screen.findByRole('option', { name: 'Ich' }));
    expect(api.patch).toHaveBeenCalledWith('c1', { assigneeSub: 'me' });
    await userEvent.click(screen.getAllByRole('button', { name: 'Aktionen für den Punkt' })[0]);
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Löschen' }));
    expect(api.remove).toHaveBeenCalledWith('c1');
  });
});
