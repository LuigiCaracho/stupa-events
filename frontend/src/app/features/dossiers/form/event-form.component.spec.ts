import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import type { CategoryRef, EventDto, EventFields } from '../api/event.models';
import { EventFormComponent } from './event-form.component';

const categories: CategoryRef[] = [{ id: 'cat-1', slug: 'kino', name: 'Kino', kind: 'format' }];
const venues = [{ id: 'v1', slug: 'kinosaal', name: 'Kinosaal' }];

async function setup(
  event: EventDto = makeEvent({ state: 'planning' }),
  draft: EventFields | null = null,
) {
  const changes: EventFields[] = [];
  const saveClicked = jest.fn();
  const view = await render(EventFormComponent, {
    inputs: { event, categories, venues, draft },
    on: { changes: (c: EventFields) => changes.push(c), saveClicked },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, changes, saveClicked };
}

describe('EventFormComponent', () => {
  it('fills the fields from the event in the zone of the event', async () => {
    await setup(
      makeEvent({ summary: 'Film', costText: '5 €', ticketUrl: 'https://tickets.example/x' }),
    );
    expect(screen.getByLabelText(/^Titel/)).toHaveValue('Movienight');
    expect(screen.getByLabelText(/Beginn, Uhrzeit/)).toHaveValue('19:00');
    expect(screen.getByLabelText('Kurztext')).toHaveValue('Film');
    expect(screen.getByLabelText('Kosten')).toHaveValue('5 €');
    expect(screen.getByLabelText('Ticket-Link')).toHaveValue('https://tickets.example/x');
    expect(screen.getByLabelText('Ort als Freitext')).toHaveValue('Kinosaal 9-133');
  });

  it('reports the complete set of changes against the event on every edit', async () => {
    const { changes } = await setup();
    await userEvent.type(screen.getByLabelText('Kurztext'), ' mehr');
    expect(changes.at(-1)).toEqual({ summary: 'Film und Popcorn mehr' });
    await userEvent.type(screen.getByLabelText('Kosten'), '5 €');
    expect(changes.at(-1)).toEqual({ summary: 'Film und Popcorn mehr', costText: '5 €' });
    await userEvent.clear(screen.getByLabelText('Kurztext'));
    expect(changes.at(-1)).toEqual({ summary: null, costText: '5 €' });
  });

  it('lays a restored draft over the event and reports it', async () => {
    const { changes } = await setup(makeEvent(), { summary: 'Entwurf' });
    expect(screen.getByLabelText('Kurztext')).toHaveValue('Entwurf');
    expect(changes.at(-1)).toEqual({ summary: 'Entwurf' });
  });

  it('locks the critical fields in live and says so; the text stays editable', async () => {
    const live = makeEvent({
      state: 'live',
      editableFields: ['summary', 'descriptionMd', 'costText'],
      lockReason: 'live_critical',
    });
    const { changes } = await setup(live);
    expect(screen.getByLabelText(/^Titel/)).toBeDisabled();
    expect(screen.getByLabelText(/Beginn, Uhrzeit/)).toBeDisabled();
    expect(screen.getByLabelText('Ticket-Link')).toBeDisabled();
    expect(screen.getAllByText('Nur über die Redaktion änderbar.').length).toBeGreaterThan(3);
    const summary = screen.getByLabelText('Kurztext');
    expect(summary).toBeEnabled();
    await userEvent.type(summary, '!');
    expect(changes.at(-1)).toEqual({ summary: 'Film und Popcorn!' });
  });

  it('locks every field in a closed dossier and hides the save button', async () => {
    await setup(makeEvent({ state: 'archived', editableFields: [], lockReason: 'closed' }));
    expect(screen.getByLabelText(/^Titel/)).toBeDisabled();
    expect(screen.getByLabelText('Beschreibung')).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Speichern' })).not.toBeInTheDocument();
  });

  it('refuses a link without https and an end before the start, and does not save', async () => {
    const { saveClicked } = await setup();
    await userEvent.type(screen.getByLabelText('Ticket-Link'), 'http://x.de');
    expect(screen.getByText('Ticket-Link muss mit https:// beginnen.')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Webseite'), 'ftp://x.de');
    expect(screen.getByText('Der Link muss mit https:// beginnen.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(saveClicked).not.toHaveBeenCalled();
  });

  it('refuses an end before the start', async () => {
    const { saveClicked } = await setup();
    const end = screen.getByLabelText(/Ende, Uhrzeit/);
    await userEvent.clear(end);
    await userEvent.type(end, '17:00');
    await userEvent.tab();
    expect(screen.getByText('Ende liegt vor dem Beginn.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(saveClicked).not.toHaveBeenCalled();
  });

  it('refuses an empty title', async () => {
    const { saveClicked } = await setup();
    await userEvent.clear(screen.getByLabelText(/^Titel/));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(screen.getByText('Titel fehlt.')).toBeInTheDocument();
    expect(saveClicked).not.toHaveBeenCalled();
  });

  it('asks to save when the form is valid', async () => {
    const { saveClicked } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(saveClicked).toHaveBeenCalled();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
