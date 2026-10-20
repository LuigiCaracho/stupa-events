import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { DocumentsApi } from '../api/documents-api.service';
import { RevisionsPanelComponent } from './revisions-panel.component';

const revisions = [
  {
    rev: 2,
    actorId: 'u',
    actorType: 'human',
    changeNote: 'Technik ergänzt',
    at: '2026-10-02T10:00:00Z',
    titleChanged: false,
    charsDelta: 20,
  },
  {
    rev: 1,
    actorId: 'u',
    actorType: 'human',
    changeNote: null,
    at: '2026-10-01T10:00:00Z',
    titleChanged: false,
    charsDelta: 100,
  },
];
const diff = {
  from: 1,
  to: 2,
  added: 1,
  removed: 0,
  lines: [{ op: 'add', text: 'neu', fromLine: null, toLine: 1 }],
};

async function setup(api: Record<string, unknown>) {
  const view = await render(RevisionsPanelComponent, {
    inputs: { documentId: 'd1', rev: 2 },
    providers: [
      { provide: DocumentsApi, useValue: { revisions: jest.fn(() => of(revisions)), ...api } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const pick = async (index: number, name: string) => {
    await userEvent.click(screen.getAllByRole('combobox')[index]);
    await userEvent.click(await screen.findByRole('option', { name }));
  };
  return { pick };
}

describe('RevisionsPanelComponent', () => {
  it('lists the revisions with their notes and compares two of them', async () => {
    const api = { diff: jest.fn(() => of(diff)) };
    const { pick } = await setup(api);
    expect(screen.getByText('Technik ergänzt')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(api.diff).not.toHaveBeenCalled();
    await pick(0, 'Fassung 1');
    await pick(1, 'Fassung 2');
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(api.diff).toHaveBeenCalledWith('d1', 1, 2);
    expect(await screen.findByText('neu')).toBeInTheDocument();
  });

  it('shows the refusal for a diff that is too large', async () => {
    const api = {
      diff: jest.fn(() =>
        throwError(
          () =>
            new HttpErrorResponse({ status: 422, error: { status: 422, code: 'diff_too_large' } }),
        ),
      ),
    };
    const { pick } = await setup(api);
    await pick(0, 'Fassung 1');
    await pick(1, 'Fassung 2');
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('zu lang für einen Vergleich');
  });

  it('offers no comparison for a single revision', async () => {
    await render(RevisionsPanelComponent, {
      inputs: { documentId: 'd1', rev: 1 },
      providers: [
        { provide: DocumentsApi, useValue: { revisions: jest.fn(() => of([revisions[1]])) } },
      ],
    });
    expect(screen.queryByRole('button', { name: 'Vergleichen' })).not.toBeInTheDocument();
  });
});
