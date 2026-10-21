import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import { OutcomeApi } from '../api/outcome-api.service';
import type { EventDto, RequiredProfile } from '../api/event.models';
import { FactsFormComponent } from './facts-form.component';

const withProfile = (profile: RequiredProfile, facts: Record<string, unknown> | null = null): EventDto =>
  makeEvent({
    facts,
    primaryCategory: { id: 'c', slug: 'x', name: 'X', kind: 'format', requiredProfile: profile },
  });

async function setup(event: EventDto, canEdit = true, putFacts = jest.fn(() => of(makeEvent({ rev: 4 })))) {
  const changed = jest.fn();
  const view = await render(FactsFormComponent, {
    inputs: { event, canEdit },
    providers: [{ provide: OutcomeApi, useValue: { putFacts } }],
    on: { changed },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, putFacts, changed, toasts: () => TestBed.inject(ToastService).toasts().map((t) => t.message) };
}

describe('FactsFormComponent', () => {
  it('shows the fields of the profile of the main category', async () => {
    await setup(withProfile('trip'));
    for (const label of ['Treffpunkt', 'Preis', 'Mindestens', 'Höchstens', 'Anmeldelink', 'Anmeldeschluss'])
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    expect(screen.queryByLabelText('Altersgrenze')).not.toBeInTheDocument();
  });

  it('falls back to the generic profile without a category', async () => {
    await setup(makeEvent({ primaryCategory: null }));
    expect(screen.getByLabelText('Plätze')).toBeInTheDocument();
    expect(screen.getByLabelText(/Budget/)).toBeInTheDocument();
  });

  it('saves a party with the age limit, a tick and the budget in cents', async () => {
    const { putFacts, changed, toasts } = await setup(withProfile('party'));
    await userEvent.click(screen.getByRole('combobox', { name: /Altersgrenze/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'Ab 16' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sicherheitskonzept liegt vor' }));
    await userEvent.type(screen.getByLabelText(/Budget/), '120');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Rahmen speichern' }));
    expect(putFacts).toHaveBeenCalledWith('ev-1', 3, {
      ageLimit: 16,
      securityPlanDone: true,
      budgetCents: 12000,
    });
    expect(changed).toHaveBeenCalledWith(expect.objectContaining({ rev: 4 }));
    expect(toasts()).toContain('Rahmen gespeichert.');
  });

  it('shows the stored facts', async () => {
    await setup(withProfile('generic', { capacity: 120, budgetCents: 50000 }));
    expect(screen.getByLabelText('Plätze')).toHaveValue(120);
  });

  it('refuses a number field with text and an http signup link without a request', async () => {
    const { putFacts } = await setup(withProfile('trip'));
    await userEvent.type(screen.getByLabelText('Mindestens'), '12');
    await userEvent.type(screen.getByLabelText('Höchstens'), '8');
    await userEvent.type(screen.getByLabelText('Anmeldelink'), 'http://x.de');
    await userEvent.click(screen.getByRole('button', { name: 'Rahmen speichern' }));
    expect(await screen.findByText('Der Link muss mit https:// beginnen.')).toBeInTheDocument();
    expect(screen.getByText('Höchstens darf nicht kleiner als Mindestens sein.')).toBeInTheDocument();
    expect(putFacts).not.toHaveBeenCalled();
  });

  it('shows the filled fields as text without the right to edit', async () => {
    await setup(withProfile('party', { ageLimit: 16, securityPlanDone: true, budgetCents: 12050, capacity: 80 }), false);
    expect(screen.queryByRole('button', { name: 'Rahmen speichern' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Plätze')).not.toBeInTheDocument();
    expect(screen.getByText('Ab 16')).toBeInTheDocument();
    expect(screen.getByText('Ja')).toBeInTheDocument();
    expect(screen.getByText('120,50 €')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
  });

  it('says so when a read-only block has no facts', async () => {
    await setup(withProfile('generic'), false);
    expect(screen.getByText('Keine Angaben.')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { view } = await setup(withProfile('party'));
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('keeps what is typed when the dossier reloads without new facts', async () => {
    const { view } = await setup(withProfile('generic'));
    await userEvent.type(screen.getByLabelText('Plätze'), '30');
    view.fixture.componentRef.setInput('event', { ...withProfile('generic'), rev: 4, title: 'Anders' });
    view.fixture.detectChanges();
    expect(screen.getByLabelText('Plätze')).toHaveValue(30);
  });
});
