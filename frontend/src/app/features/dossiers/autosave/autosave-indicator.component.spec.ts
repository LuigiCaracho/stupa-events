import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../testing/a11y';
import type { SaveStatus } from './draft-autosave';
import { AutosaveIndicatorComponent } from './autosave-indicator.component';

describe('AutosaveIndicatorComponent', () => {
  it.each([
    ['saving', 'Speichert …'],
    ['unsaved', 'Nicht gespeichert'],
    ['offline', 'Nicht gespeichert, offline'],
    ['conflict', 'Konflikt, bitte prüfen'],
  ] as [SaveStatus, string][])('says "%s" in a polite live region', async (status, text) => {
    await render(AutosaveIndicatorComponent, { inputs: { status } });
    expect(screen.getByRole('status')).toHaveTextContent(text);
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });

  it('shows the time of the last save', async () => {
    const { container } = await render(AutosaveIndicatorComponent, {
      inputs: { status: 'saved', savedAt: new Date(2026, 9, 18, 14, 2) },
    });
    expect(screen.getByRole('status')).toHaveTextContent('Gespeichert 14:02');
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('keeps the region but says nothing when idle', async () => {
    await render(AutosaveIndicatorComponent, { inputs: { status: 'idle' } });
    expect(screen.getByRole('status')).toHaveTextContent('');
  });
});
