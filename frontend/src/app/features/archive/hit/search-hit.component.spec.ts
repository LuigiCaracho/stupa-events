import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeHit } from '../../../../testing/m5-fixtures';
import { SearchHitComponent } from './search-hit.component';

describe('SearchHitComponent', () => {
  it('draws the highlight segments of the title as mark elements and nothing as HTML', async () => {
    const { container } = await render(SearchHitComponent, {
      inputs: {
        hit: makeHit({
          title: '<b>Fach</b>schaftssitzung',
          highlights: [
            {
              field: 'title',
              segments: [
                { text: '<b>Fach</b>', hit: true },
                { text: 'schaftssitzung', hit: false },
              ],
            },
          ],
        }),
        query: 'fach',
      },
    });
    expect(container.querySelectorAll('mark')).toHaveLength(1);
    expect(container.querySelector('mark')?.textContent).toBe('<b>Fach</b>');
    expect(container.querySelector('b')).toBeNull();
  });

  it('marks the query words itself when the server sent no highlight (typo hit)', async () => {
    const { container } = await render(SearchHitComponent, {
      inputs: { hit: makeHit({ title: 'Kinoabend' }), query: 'kino' },
    });
    expect(container.querySelector('mark')).toHaveTextContent('Kino');
  });

  it('shows a snippet per matching field with its label, the state and the review date', async () => {
    await render(SearchHitComponent, {
      inputs: {
        hit: makeHit({
          howtoVerifiedAt: '2026-02-12T10:00:00Z',
          highlights: [
            { field: 'body', segments: [{ text: 'Popcorn', hit: true }, { text: 'maschine', hit: false }] },
          ],
        }),
      },
    });
    expect(screen.getByText('Text')).toBeInTheDocument();
    expect(screen.getByText('Popcorn')).toBeInTheDocument();
    expect(screen.getByText('Archiv')).toBeInTheDocument();
    expect(screen.getByText(/Anleitung geprüft am 12\.02\.2026/)).toBeInTheDocument();
  });

  it('warns in text when the howto is unverified and says the dossier is of another organization', async () => {
    await render(SearchHitComponent, {
      inputs: { hit: makeHit({ howtoUnverified: true, foreign: true }) },
    });
    expect(screen.getByText('Anleitung ungeprüft')).toBeInTheDocument();
    expect(screen.getByText('Andere Organisation')).toBeInTheDocument();
  });

  it('emits open, and "Neu aus Vorlage" only for a dossier that can be a template', async () => {
    const open = jest.fn();
    const useTemplate = jest.fn();
    const view = await render(SearchHitComponent, {
      inputs: { hit: makeHit() },
      on: { open, useTemplate },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Öffnen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Neu aus Vorlage' }));
    expect(open).toHaveBeenCalledWith(expect.objectContaining({ id: 'ev-9' }));
    expect(useTemplate).toHaveBeenCalled();
    view.fixture.componentRef.setInput('hit', makeHit({ state: 'live', foreign: true }));
    view.fixture.detectChanges();
    expect(screen.queryByRole('button', { name: 'Neu aus Vorlage' })).not.toBeInTheDocument();
    view.fixture.componentRef.setInput('hit', makeHit({ kind: 'document' }));
    view.fixture.detectChanges();
    expect(screen.queryByRole('button', { name: 'Neu aus Vorlage' })).not.toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = await render(SearchHitComponent, { inputs: { hit: makeHit() } });
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('has no state text for a document hit and ignores snippets of unknown fields', async () => {
    await render(SearchHitComponent, {
      inputs: {
        hit: makeHit({
          kind: 'document',
          state: undefined,
          highlights: [{ field: 'mystery', segments: [{ text: 'Treffer', hit: true }] }],
        }),
      },
    });
    expect(screen.queryByText('Archiv')).not.toBeInTheDocument();
    expect(screen.getByText('Treffer')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Neu aus Vorlage' })).not.toBeInTheDocument();
  });

  it('offers "Neu aus Vorlage" for an own live or follow-up dossier', async () => {
    const view = await render(SearchHitComponent, { inputs: { hit: makeHit({ state: 'live' }) } });
    expect(screen.getByRole('button', { name: 'Neu aus Vorlage' })).toBeInTheDocument();
    view.fixture.componentRef.setInput('hit', makeHit({ state: 'followup' }));
    view.fixture.detectChanges();
    expect(screen.getByRole('button', { name: 'Neu aus Vorlage' })).toBeInTheDocument();
    view.fixture.componentRef.setInput('hit', makeHit({ state: 'planning' }));
    view.fixture.detectChanges();
    expect(screen.queryByRole('button', { name: 'Neu aus Vorlage' })).not.toBeInTheDocument();
  });
});
