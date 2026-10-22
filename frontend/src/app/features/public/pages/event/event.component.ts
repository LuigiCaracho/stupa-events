/**
 * P04 Event-Detail (`/e/:slug`): poster, state banner, key facts in Berlin time, the buttons "In Kalender", "Ticket" and
 * "Teilen", the description from the server (sanitized again by Angular) and more of the same series. The server
 * sends the page head (Open Graph, JSON-LD) for the same path; the app loads the data again. An unknown or withdrawn
 * event looks the same: 404, no detail that would give a draft away.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { resourceValue } from '@core/api/resource-value';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, IconComponent, ToastService } from '@stupa-makers/ui-kit';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import { whenText } from '../../model/event-format';
import { EventPosterComponent } from '../../ui/event-poster/event-poster.component';
import { EventRowComponent } from '../../ui/event-row/event-row.component';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';
import { ShareService } from '../../ui/share.service';

const web = (url: string | null): string | null => (url && /^https?:\/\//i.test(url) ? url : null);

@Component({
  selector: 'app-event-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    IconComponent,
    EmptyStateComponent,
    NoteComponent,
    SkeletonComponent,
    EventPosterComponent,
    EventRowComponent,
    LinkButtonComponent,
    LoadErrorComponent,
  ],
  templateUrl: './event.component.html',
  styleUrl: './event.component.scss',
})
export class EventPageComponent {
  private readonly api = inject(PublicApi);
  private readonly share = inject(ShareService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly slug = input.required<string>();
  protected readonly data = rxResource({
    params: () => this.slug(),
    stream: ({ params }) => this.api.event(params),
  });
  protected readonly event = computed(() => resourceValue(this.data, undefined));
  protected readonly error = computed(() =>
    this.data.error() ? publicErrorOf(this.data.error()) : null,
  );
  protected readonly shareUrl = signal<string | null>(null);

  protected readonly when = computed(() => (this.event() ? whenText(this.event()!) : ''));
  protected readonly ticket = computed(() => web(this.event()?.ticketUrl ?? null));
  protected readonly website = computed(() => web(this.event()?.websiteUrl ?? null));
  protected readonly canceled = computed(() => this.event()?.status === 'cancelled');
  protected readonly bannerText = computed(() => {
    const e = this.event();
    if (!e || e.status === 'scheduled') return null;
    const reason = e.statusReason?.text;
    if (e.status === 'cancelled') {
      return reason
        ? this.i18n.translate('public.event.cancelledReason', { reason })
        : this.i18n.translate('publicStatus.cancelled');
    }
    return reason
      ? this.i18n.translate('public.event.postponedReason', { reason })
      : this.i18n.translate('public.event.postponed');
  });
  protected readonly venueLine = computed(() => {
    const v = this.event()?.venue;
    return v ? [v.address, v.city].filter(Boolean).join(', ') : '';
  });
  protected readonly mainCategory = computed(() => this.event()?.categories[0] ?? null);

  constructor() {
    usePageTitle(() => this.event()?.title ?? null);
  }

  protected async onShare(): Promise<void> {
    const e = this.event();
    if (!e) return;
    const url = `${this.share.origin}${e.path}`;
    const result = await this.share.share({ title: e.title, url });
    if (result === 'copied') this.toast.success(this.i18n.translate('public.event.copied'));
    this.shareUrl.set(result === 'failed' ? url : null);
  }

  protected reload(): void {
    this.data.reload();
  }
}
