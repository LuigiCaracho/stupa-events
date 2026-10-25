/**
 * The iOS install hint (B4): Safari on iOS has no install prompt, so a short line shows how to add the site to the
 * home screen. It shows only in iOS Safari, only outside the installed app, only until it was closed once and never
 * together with the update prompt. The "closed" state is a convenience in `localStorage`; where it is blocked the hint
 * falls back to `sessionStorage` and, with no storage at all, stays away.
 */
import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { IS_INSTALLED_APP } from '@core/browser/installed-app.token';
import { isIosSafari } from '@core/browser/ios-safari';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { SwUpdateService } from '@core/pwa/sw-update.service';
import { ButtonComponent } from '@stupa-makers/ui-kit';

const KEY = 'ev.installHint';

function closed(win: Window): boolean {
  for (const store of ['localStorage', 'sessionStorage'] as const) {
    try {
      return win[store].getItem(KEY) === '1';
    } catch {
      continue;
    }
  }
  return true;
}

function remember(win: Window): void {
  for (const store of ['localStorage', 'sessionStorage'] as const) {
    try {
      win[store].setItem(KEY, '1');
    } catch {
      continue;
    }
  }
}

@Component({
  selector: 'app-install-hint',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent],
  templateUrl: './install-hint.component.html',
  styleUrl: './install-hint.component.scss',
})
export class InstallHintComponent {
  private readonly win = inject(DOCUMENT).defaultView as Window;
  private readonly sw = inject(SwUpdateService);
  private readonly installed = inject(IS_INSTALLED_APP);
  private readonly dismissed = signal(closed(this.win));

  protected readonly visible = computed(
    () =>
      !this.dismissed() &&
      !this.sw.updateReady() &&
      isIosSafari(this.win.navigator) &&
      !this.installed(),
  );

  protected close(): void {
    remember(this.win);
    this.dismissed.set(true);
  }
}
