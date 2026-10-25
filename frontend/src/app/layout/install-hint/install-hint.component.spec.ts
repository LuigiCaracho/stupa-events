/** Spec for the iOS install hint: where it shows, that it closes for good and that it yields to the update prompt. */
import { signal } from '@angular/core';
import { IS_INSTALLED_APP } from '@core/browser/installed-app.token';
import { SwUpdateService } from '@core/pwa/sw-update.service';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../testing/a11y';
import { InstallHintComponent } from './install-hint.component';

const IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';

async function setup(opts: { ua?: string; installed?: boolean; updateReady?: boolean } = {}) {
  jest.spyOn(window.navigator, 'userAgent', 'get').mockReturnValue(opts.ua ?? IPHONE);
  return render(InstallHintComponent, {
    providers: [
      { provide: IS_INSTALLED_APP, useValue: () => opts.installed ?? false },
      { provide: SwUpdateService, useValue: { updateReady: signal(opts.updateReady ?? false) } },
    ],
  });
}

describe('InstallHintComponent', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => jest.restoreAllMocks());

  it('tells iOS Safari users how to install', async () => {
    await setup();
    expect(
      screen.getByText('Zum Installieren: Tippe auf Teilen und dann auf „Zum Home-Bildschirm“.'),
    ).toBeInTheDocument();
  });

  it('stays away in other browsers, in the installed app and while an update waits', async () => {
    await setup({ ua: 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130' });
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });

  it('stays away in the installed app', async () => {
    await setup({ installed: true });
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });

  it('yields to the update prompt', async () => {
    await setup({ updateReady: true });
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });

  it('closes for good', async () => {
    await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Schließen' }));
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
    expect(localStorage.getItem('ev.installHint')).toBe('1');
  });

  it('does not show again once closed', async () => {
    localStorage.setItem('ev.installHint', '1');
    await setup();
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });

  it('falls back to the session where localStorage is blocked, and shows nothing without any storage', async () => {
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    await setup();
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = await setup();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
