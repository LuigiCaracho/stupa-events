import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { CommentsApi } from '../api/comments-api.service';
import type { AttachmentOut } from '../model/attachment.models';
import { AttachmentRowComponent } from './attachment-row.component';

const file = (o: Partial<AttachmentOut> = {}): AttachmentOut => ({
  id: 'a1',
  kind: 'business_plan',
  displayName: 'plan.pdf',
  mime: 'application/pdf',
  sizeBytes: 2_621_440,
  visibility: 'org',
  scanStatus: 'clean',
  altText: null,
  credit: null,
  rightsBasis: null,
  licenseRef: null,
  sourceUrl: null,
  personsDepicted: false,
  consentNote: null,
  containsDate: null,
  datedFor: null,
  meta: {},
  supersedesId: null,
  retiredAt: null,
  createdAt: '2026-10-01T10:00:00Z',
  hasPreview: false,
  replacedBy: null,
  ...o,
});

async function setup(attachment: AttachmentOut, inputs: Record<string, unknown> = {}) {
  const command = jest.fn();
  const showQuestions = jest.fn();
  const view = await render(AttachmentRowComponent, {
    inputs: {
      attachment,
      eventId: 'e1',
      canEdit: true,
      downloadHref: '/dl',
      previewHref: '/pv',
      ...inputs,
    },
    on: { command, showQuestions },
    providers: [{ provide: CommentsApi, useValue: { add: jest.fn() } }],
  });
  return { ...view, command, showQuestions };
}

describe('AttachmentRowComponent', () => {
  it('links a clean file and shows size, kind, visibility and the scan status as text', async () => {
    const { container } = await setup(file());
    expect(screen.getByRole('link', { name: 'plan.pdf' })).toHaveAttribute('href', '/dl');
    expect(screen.getByText('Businessplan')).toBeInTheDocument();
    expect(screen.getByText('2,5 MB')).toBeInTheDocument();
    expect(screen.getByText('Organisation')).toBeInTheDocument();
    expect(screen.getByText('Geprüft')).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it.each([
    ['pending', 'Wird geprüft'],
    ['infected', 'Abgelehnt: Schadsoftware gefunden'],
    ['error', 'Prüfung fehlgeschlagen'],
  ] as const)('gives no link while the scan is %s', async (scanStatus, text) => {
    await setup(file({ scanStatus }));
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('shows the preview, alt text, consent and the mark "Rückfrage offen"', async () => {
    const { showQuestions } = await setup(
      file({
        kind: 'social_post',
        hasPreview: true,
        altText: 'Bühne',
        personsDepicted: true,
        consentNote: 'liegt vor',
      }),
      { openQuestion: true },
    );
    expect(screen.getByAltText('Bühne')).toBeInTheDocument();
    expect(screen.getByText('Einwilligung: liegt vor')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage offen' }));
    expect(showQuestions).toHaveBeenCalled();
  });

  it('offers replace, hide and the visibility, without "Alle Mitglieder" for a plan', async () => {
    const { command } = await setup(file());
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Anhang' }));
    expect(
      screen.queryByRole('menuitemcheckbox', { name: 'Alle Mitglieder' }),
    ).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Ersetzen' }));
    expect(command).toHaveBeenCalledWith({ name: 'replace' });
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Anhang' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Ausblenden' }));
    expect(command).toHaveBeenCalledWith({ name: 'retire' });
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Anhang' }));
    await userEvent.click(
      await screen
        .findByRole('menuitemradio', { name: 'Team' })
        .catch(() => screen.findByText('Team')),
    );
    expect(command).toHaveBeenCalledWith({ name: 'visibility', value: 'team' });
  });

  it('has no menu for a reader', async () => {
    await setup(file(), { canEdit: false });
    expect(
      screen.queryByRole('button', { name: 'Aktionen für den Anhang' }),
    ).not.toBeInTheDocument();
  });
});
