import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import type { RevisionDetail, RevisionOut } from '../api/action.models';
import { EventsApi } from '../api/events-api.service';
import { RevisionCompareComponent } from './revision-compare.component';

const revisions = [3, 2, 1].map((rev) => ({ rev })) as unknown as RevisionOut[];
const detail = (rev: number, snapshot: Record<string, unknown>) =>
  ({ rev, snapshot }) as unknown as RevisionDetail;

async function setup(revision = jest.fn()) {
  await render(RevisionCompareComponent, {
    inputs: { eventId: 'e1', revisions },
    providers: [{ provide: EventsApi, useValue: { revision } }],
  });
  const pick = async (index: number, name: string) => {
    await userEvent.click(screen.getAllByRole('combobox')[index]);
    await userEvent.click(await screen.findByRole('option', { name }));
  };
  return { pick, revision };
}

describe('RevisionCompareComponent', () => {
  it('shows short fields in the config diff and long texts as a line diff', async () => {
    const revision = jest.fn((_id: string, rev: number) =>
      of(
        rev === 1
          ? detail(1, { title: 'Alt', descriptionMd: 'a\nb', same: 1 })
          : detail(3, { title: 'Neu', descriptionMd: 'a\nc', same: 1, extra: null }),
      ),
    );
    const { pick } = await setup(revision);
    await pick(0, 'Fassung 1');
    await pick(1, 'Fassung 3');
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(revision).toHaveBeenCalledTimes(2);
    expect(await screen.findByText('Beschreibung')).toBeInTheDocument();
    expect(screen.getByText('Entfernt:')).toBeInTheDocument();
    expect(screen.getByText('Hinzugefügt:')).toBeInTheDocument();
    expect(screen.getByText('Titel')).toBeInTheDocument();
  });

  it('says so when nothing differs', async () => {
    const { pick } = await setup(jest.fn(() => of(detail(1, { title: 'x' }))));
    await pick(0, 'Fassung 1');
    await pick(1, 'Fassung 3');
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(
      await screen.findByText('Zwischen diesen Fassungen gibt es keinen Unterschied.'),
    ).toBeInTheDocument();
  });

  it('skips a long text that is too long for the line diff', async () => {
    const big = Array.from({ length: 2001 }, (_, i) => `l${i}`).join('\n');
    const { pick } = await setup(
      jest.fn((_i: string, rev: number) =>
        of(detail(rev, { descriptionMd: rev === 1 ? big : 'x' })),
      ),
    );
    await pick(0, 'Fassung 1');
    await pick(1, 'Fassung 3');
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(
      await screen.findByText('Zwischen diesen Fassungen gibt es keinen Unterschied.'),
    ).toBeInTheDocument();
  });

  it('shows the refusal and does nothing before both are chosen', async () => {
    const revision = jest.fn(() =>
      throwError(
        () => new HttpErrorResponse({ status: 404, error: { status: 404, code: 'not_found' } }),
      ),
    );
    const { pick } = await setup(revision);
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(revision).not.toHaveBeenCalled();
    await pick(0, 'Fassung 1');
    await pick(1, 'Fassung 3');
    await userEvent.click(screen.getByRole('button', { name: 'Vergleichen' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Diese Seite gibt es nicht');
  });
});
