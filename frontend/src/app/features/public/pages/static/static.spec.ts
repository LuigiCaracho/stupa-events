/** Spec for the legal placeholders and the offline page. */
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../../testing/a11y';
import { LegalPageComponent } from './legal.component';
import { OfflinePageComponent } from './offline.component';

describe('LegalPageComponent', () => {
  it.each([
    ['imprint', 'Impressum'],
    ['privacy', 'Datenschutz'],
  ] as const)('shows the %s placeholder without invented content', async (kind, heading) => {
    const { container } = await render(LegalPageComponent, { inputs: { kind } });
    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument();
    expect(
      screen.getByText(
        'Dieser Text wird mit der Hochschule und der Datenschutzbeauftragten abgestimmt und ergänzt.',
      ),
    ).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe('OfflinePageComponent', () => {
  it('says the visitor is offline and points to Heute', async () => {
    const { container } = await render(OfflinePageComponent, { providers: [provideRouter([])] });
    expect(screen.getByRole('heading', { level: 1, name: 'Du bist offline.' })).toBeInTheDocument();
    expect(screen.getByText('Zuletzt geladene Termine siehst du unter Heute.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zu Heute' })).toHaveAttribute('href', '/');
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
