/**
 * P07 Abos (`/abos`, anchor `#k=<slug>`): the calendar subscription addresses. One calendar for everything and one per
 * category, each as a `webcal:` link that opens the calendar app and as an `https` address to copy. The personal part
 * (interests, calendar and mail) starts at Get started (`/start`); "Verwaltungslink anfordern" asks for the magic link
 * of the manage page. No QR codes yet.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { resourceValue } from '@core/api/resource-value';
import { rxResource, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, DialogComponent, ToastService } from '@stupa-makers/ui-kit';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import {
  ALL_ICS,
  type SubscribeLinks,
  anchoredCategory,
  categoryIcs,
  subscribeLinks,
} from '../../model/subscribe-links';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { ManageLinkFormComponent } from '../../ui/manage-link-form/manage-link-form.component';
import { usePageTitle } from '../../ui/page-title';
import { ShareService } from '../../ui/share.service';

@Component({
  selector: 'app-subscribe-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    DialogComponent,
    EmptyStateComponent,
    NoteComponent,
    SkeletonComponent,
    LinkButtonComponent,
    LoadErrorComponent,
    ManageLinkFormComponent,
  ],
  templateUrl: './subscribe.component.html',
  styleUrl: './subscribe.component.scss',
})
export class SubscribePageComponent {
  private readonly api = inject(PublicApi);
  private readonly share = inject(ShareService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);
  private readonly route = inject(ActivatedRoute);

  protected readonly data = rxResource({ stream: () => this.api.categories() });
  private readonly fragment = toSignal(this.route.fragment, {
    initialValue: this.route.snapshot.fragment,
  });
  protected readonly marked = computed(() => anchoredCategory(this.fragment()));
  protected readonly copyFailed = signal(false);
  protected readonly manageOpen = signal(false);
  protected readonly loaded = computed(() => resourceValue(this.data, undefined));
  protected readonly error = computed(() =>
    this.data.error() ? publicErrorOf(this.data.error()) : null,
  );

  protected readonly all = subscribeLinks(this.share.origin, ALL_ICS);
  protected readonly rows = computed(() =>
    (resourceValue(this.data, undefined) ?? []).map((c) => ({
      ...c,
      links: subscribeLinks(this.share.origin, categoryIcs(c.slug)),
    })),
  );

  constructor() {
    usePageTitle(() => this.i18n.translate('public.subscribe.title'));
    effect(() => {
      const slug = this.marked();
      if (!slug || !resourceValue(this.data, undefined)) return;
      queueMicrotask(() =>
        document.getElementById(`k-${slug}`)?.scrollIntoView({ block: 'center' }),
      );
    });
  }

  protected async copy(links: SubscribeLinks): Promise<void> {
    const ok = await this.share.copy(links.https);
    this.copyFailed.set(!ok);
    if (ok) this.toast.success(this.i18n.translate('public.subscribe.copied'));
  }

  protected reload(): void {
    this.data.reload();
  }
}
