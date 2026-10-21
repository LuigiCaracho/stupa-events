/**
 * The command palette (Strg/Cmd+K) of the signed-in frame (M5 contract 6.3, 11.5). Pattern from STUPA-Workflow@93c33d6
 * frontend/src/app/features/search/command-palette.component.ts (rewritten, no code copied). An `app-dialog` (a sheet
 * on the phone) with a combobox and a listbox in four groups: Dossiers and Formate from the search (two parallel
 * requests, 200 ms after the last key, an older answer never replaces a newer one), Aktionen and Navigation filtered
 * locally by the permissions of the person. The arrow keys move through the options (`aria-activedescendant`), Enter runs
 * the active one, Esc closes and the focus returns to where it was. The number of results goes to a live region.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { Router } from '@angular/router';
import type { Subscription } from 'rxjs';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { DialogComponent } from '@stupa-makers/ui-kit';
import { ArchiveApi } from '../../features/archive/api/archive-api.service';
import type { SearchHit } from '../../features/archive/model/archive.models';
import { DossierCommands } from '../../features/dossiers/api/dossier-commands';
import { AuthService } from '@core/auth/auth.service';
import { NavService } from '../nav.service';
import { type PaletteItem, dossierIdOf, matches, toGroups } from './palette-items';
import { PaletteService } from './palette.service';

const DELAY_MS = 200;
let nextId = 0;

@Component({
  selector: 'app-command-palette',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, DialogComponent],
  templateUrl: './command-palette.component.html',
  styleUrl: './command-palette.component.scss',
})
export class CommandPaletteComponent {
  protected readonly palette = inject(PaletteService);
  private readonly router = inject(Router);
  private readonly api = inject(ArchiveApi);
  private readonly nav = inject(NavService);
  private readonly auth = inject(AuthService);
  private readonly i18n = inject(I18nService);
  private readonly commands = inject(DossierCommands);

  private readonly input = viewChild<ElementRef<HTMLInputElement>>('field');
  protected readonly uid = `pal-${nextId++}`;
  protected readonly q = signal('');
  private readonly applied = signal('');
  protected readonly active = signal(0);
  private readonly events = signal<SearchHit[]>([]);
  private readonly formats = signal<SearchHit[]>([]);
  protected readonly failure = signal<'rate' | 'error' | null>(null);
  private timer: ReturnType<typeof setTimeout> | undefined;
  private eventsCall?: Subscription;
  private formatsCall?: Subscription;
  private readonly url = signal(this.router.url);

  private readonly actionItems = computed<PaletteItem[]>(() => {
    const t = this.i18n.translate.bind(this.i18n);
    const list: PaletteItem[] = [];
    if (this.auth.can('event.create')) {
      list.push(
        {
          id: 'a:new',
          group: 'actions',
          label: t('palette.action.new'),
          run: () => this.go('/dossiers/neu'),
        },
        {
          id: 'a:template',
          group: 'actions',
          label: t('palette.action.template'),
          run: () => this.go('/dossiers/neu', { modus: 'vorlage' }),
        },
      );
    }
    if (dossierIdOf(this.url()) && this.commands.allowed().includes('save-as-format')) {
      list.push({
        id: 'a:format',
        group: 'actions',
        label: t('palette.action.saveAsFormat'),
        run: () => this.commands.send('save-as-format'),
      });
    }
    return list;
  });
  private readonly navItems = computed<PaletteItem[]>(() =>
    this.nav.visible().map((n) => ({
      id: `n:${n.key}`,
      group: 'nav' as const,
      label: this.i18n.translate(n.labelKey),
      run: () => this.go(n.path),
    })),
  );
  private readonly remoteItems = computed<PaletteItem[]>(() => [
    ...this.events().map((h) => this.hitItem(h, 'events')),
    ...this.formats().map((h) => this.hitItem(h, 'formats')),
  ]);

  protected readonly groups = computed(() => {
    const q = this.q();
    const local = [...this.actionItems(), ...this.navItems()].filter((i) => matches(i, q));
    return toGroups([...this.remoteItems(), ...local]);
  });
  protected readonly flat = computed(() => this.groups().flatMap((g) => g.items));
  protected readonly activeId = computed(() => {
    const item = this.flat()[this.active()];
    return item ? this.optionId(item) : null;
  });
  protected readonly announce = computed(() =>
    this.i18n.translate('palette.count', { count: this.flat().length }),
  );

  constructor() {
    effect(() => {
      if (!this.palette.isOpen()) return;
      untracked(() => {
        // A search typed in the last session must not land in this one (its delay may still run).
        clearTimeout(this.timer);
        this.eventsCall?.unsubscribe();
        this.formatsCall?.unsubscribe();
        this.url.set(this.router.url);
        this.q.set('');
        this.applied.set('');
        this.events.set([]);
        this.formats.set([]);
        this.failure.set(null);
        this.active.set(0);
        setTimeout(() => this.input()?.nativeElement.focus());
      });
    });
    effect(() => {
      const q = this.applied();
      untracked(() => this.fetch(q));
    });
    effect(() => {
      this.flat();
      untracked(() => this.active.set(0));
    });
    effect(() => {
      const id = this.activeId();
      if (id) document.getElementById(id)?.scrollIntoView?.({ block: 'nearest' });
    });
    inject(DestroyRef).onDestroy(() => clearTimeout(this.timer));
  }

  protected optionId(item: PaletteItem): string {
    return `${this.uid}-${item.id}`;
  }

  protected isActive(item: PaletteItem): boolean {
    return this.flat()[this.active()]?.id === item.id;
  }

  protected typed(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.q.set(value);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.applied.set(value.trim()), DELAY_MS);
  }

  protected onKey(event: KeyboardEvent): void {
    const count = this.flat().length;
    if (count === 0) return;
    const move = (to: number): void => {
      event.preventDefault();
      this.active.set(to);
    };
    switch (event.key) {
      case 'ArrowDown':
        return move((this.active() + 1) % count);
      case 'ArrowUp':
        return move((this.active() + count - 1) % count);
      case 'Home':
        return move(0);
      case 'End':
        return move(count - 1);
      case 'Enter':
        event.preventDefault();
        return this.run(this.flat()[this.active()]);
    }
  }

  protected run(item: PaletteItem): void {
    this.palette.hide();
    item.run();
  }

  protected hover(item: PaletteItem): void {
    const at = this.flat().findIndex((i) => i.id === item.id);
    if (at >= 0) this.active.set(at);
  }

  private fetch(q: string): void {
    this.eventsCall?.unsubscribe();
    this.formatsCall?.unsubscribe();
    this.failure.set(null);
    if (q.length < 2) {
      this.events.set([]);
      this.formats.set([]);
      return;
    }
    const fail = (items: { set(v: SearchHit[]): void }) => (error: unknown) => {
      items.set([]);
      this.failure.set((error as { status?: number }).status === 429 ? 'rate' : 'error');
    };
    this.eventsCall = this.api.search({ q, scope: 'events', limit: 5 }).subscribe({
      next: (out) => this.events.set(out.hits),
      error: fail(this.events),
    });
    this.formatsCall = this.api.search({ q, scope: 'formats', limit: 3 }).subscribe({
      next: (out) => this.formats.set(out.hits),
      error: fail(this.formats),
    });
  }

  private hitItem(hit: SearchHit, group: 'events' | 'formats'): PaletteItem {
    return {
      id: `${group}:${hit.id}`,
      group,
      label: hit.title,
      hint: hit.subtitle,
      run: () =>
        group === 'formats'
          ? void this.router.navigateByUrl(hit.link)
          : this.go(hit.foreign ? `/archiv/${hit.id}` : `/dossiers/${hit.id}`),
    };
  }

  private go(path: string, queryParams?: Record<string, string>): void {
    void this.router.navigate([path], queryParams ? { queryParams } : undefined);
  }
}
