/** Frame of the admin area: page title, one tab per page the principal may open, and the outlet below. */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { type TabItem, TabsComponent } from '@stupa-makers/ui-kit';
import { filter, map, startWith } from 'rxjs';
import { ADMIN_TABS } from '../admin-tabs';

@Component({
  selector: 'app-admin-frame',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, TranslatePipe, PageHeaderComponent, TabsComponent],
  templateUrl: './admin-frame.component.html',
  styleUrl: './admin-frame.component.scss',
})
export class AdminFrameComponent {
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly i18n = inject(I18nService);

  protected readonly tabs = computed<TabItem[]>(() =>
    ADMIN_TABS.filter((t) => this.auth.can(t.permission)).map((t) => ({
      id: t.id,
      label: this.i18n.translate(t.labelKey),
    })),
  );

  protected readonly active = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      startWith(null),
      map(() => this.router.url.split(/[?#]/)[0].split('/')[2] ?? null),
    ),
    { initialValue: null },
  );

  protected go(id: string | null): void {
    if (id && id !== this.active()) void this.router.navigate(['/verwaltung', id]);
  }
}
