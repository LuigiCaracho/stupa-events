/**
 * I18, detail side (`/formate/:slug`): name, organization and description, the tabs "Anleitung" (master howto in the
 * editor, "Zuletzt geprüft …", "Als geprüft markieren"), "Ausgaben" (with attendance and actual costs) and "Checkliste
 * und Mails" (the template of the profile, read only), the card "Letzte Ausgabe" and the button "Neue Ausgabe". Writing
 * needs `format.manage` or `event.submit` in the organization of the format; without it the page is read only, and a 403
 * of the server wins either way.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { problemOf } from '@core/api/problem';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMoney } from '@shared/format.util';
import { MarkdownViewComponent } from '@shared/markdown/markdown-view.component';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent, TabsComponent, ToastService, type TabItem } from '@stupa-makers/ui-kit';
import { formatEventDay } from '@shared/event-time';
import { problemMessage } from '../../dossiers/api/problem-message';
import { DocumentEditorComponent } from '../../dossiers/editor/document-editor.component';
import { FormatsApi } from '../api/formats-api.service';
import type { FormatEdition, FormatOut } from '../model/format.models';
import { FormatEditionsComponent } from './format-editions.component';
import { NewEditionDialogComponent } from './new-edition-dialog.component';
import { resourceValue } from '@core/api/resource-value';

type FormatTab = 'howto' | 'editions' | 'checklist';

@Component({
  selector: 'app-format-detail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    LocalizedDatePipe,
    TranslatePipe,
    ButtonComponent,
    DocumentEditorComponent,
    EmptyStateComponent,
    FormatEditionsComponent,
    MarkdownViewComponent,
    NewEditionDialogComponent,
    NoteComponent,
    PageHeaderComponent,
    SkeletonComponent,
    StatusTextComponent,
    TabsComponent,
  ],
  templateUrl: './format-detail.component.html',
  styleUrl: './format-detail.component.scss',
})
export class FormatDetailComponent {
  private readonly api = inject(FormatsApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly slug = input.required<string>();

  protected readonly loaded = rxResource({
    params: () => this.slug(),
    stream: ({ params }) => this.api.get(params),
  });
  protected readonly format = computed(() => resourceValue<FormatOut | null>(this.loaded, null));
  protected readonly tab = signal<FormatTab>('howto');
  protected readonly busy = signal(false);
  protected readonly dialogOpen = signal(false);

  /** The next ones are only read while a format is shown. */
  protected readonly canManage = computed(() => {
    const slug = (this.format() as FormatOut).organization?.slug;
    return (
      this.auth.can('format.manage') ||
      (this.auth.can('event.submit') && this.auth.organizations().some((o) => o.slug === slug))
    );
  });
  protected readonly latest = computed<FormatEdition | null>(() => {
    const list = [...(this.format() as FormatOut).editions];
    list.sort((a, b) => b.startsAt.localeCompare(a.startsAt));
    return list[0] ?? null;
  });
  protected readonly stale = computed(() => (this.format() as FormatOut).howtoStale);
  protected readonly tabs = computed<TabItem[]>(() => {
    const f = this.format() as FormatOut;
    return [
      { id: 'howto', label: this.i18n.translate('format.tabHowto') },
      {
        id: 'editions',
        label: this.i18n.translate('format.tabEditions'),
        ...(f.editions.length ? { count: f.editions.length } : {}),
      },
      { id: 'checklist', label: this.i18n.translate('format.tabChecklist') },
    ];
  });

  protected money(cents: number): string {
    return formatMoney(this.i18n, cents, 'EUR');
  }

  protected day(e: FormatEdition): string {
    return formatEventDay(e.startsAt, 'Europe/Berlin');
  }

  protected newEdition(): void {
    const f = this.format() as FormatOut;
    if (f.editions.length > 0)
      void this.router.navigate(['/dossiers/neu'], { queryParams: { format: f.slug } });
    else this.dialogOpen.set(true);
  }

  protected created(id: string): void {
    this.dialogOpen.set(false);
    void this.router.navigate(['/dossiers', id]);
  }

  protected createHowto(fromEvent: boolean): void {
    this.run(this.api.createHowto(this.slug(), fromEvent ? this.latest()?.id : undefined));
  }

  protected verify(): void {
    this.run(this.api.verify(this.slug()), 'format.verified');
  }

  protected reload(): void {
    this.loaded.reload();
  }

  protected openEdition(edition: FormatEdition): void {
    void this.router.navigate(edition.foreign ? ['/archiv', edition.id] : ['/dossiers', edition.id]);
  }

  private run(call: ReturnType<FormatsApi['verify']>, done?: 'format.verified'): void {
    this.busy.set(true);
    call.subscribe({
      next: () => {
        this.busy.set(false);
        if (done) this.toast.success(this.i18n.translate(done));
        this.loaded.reload();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
