/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/shell.component.ts */
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { SwUpdatePromptComponent } from '@core/pwa/sw-update-prompt.component';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { MEDIA, ToastComponent } from '@stupa-makers/ui-kit';
import { BottomBarComponent } from './bottom-bar/bottom-bar.component';
import { InboxComponent } from '../features/notifications/inbox.component';
import { LoadBarComponent } from './load-bar/load-bar.component';
import { mediaQuerySignal } from './media-query';
import { NavRailComponent } from './nav-rail/nav-rail.component';
import { CommandPaletteComponent } from './palette/command-palette.component';
import { PageFrameService } from './page-frame.service';
import { PaletteService } from './palette/palette.service';
import { PublicHeaderComponent } from './public-header/public-header.component';
import { SiteFooterComponent } from './site-footer/site-footer.component';

/**
 * The frame around a page.
 *
 * - `rail`: a signed-in principal. The navigation rail at the start edge, or the bottom
 *   bar on a phone. The branded footer shows only on a route with `footer: true` (the
 *   start page and the public pages).
 * - `public`: nobody signed in. The public top bar and the branded footer, always.
 * - `bare`: route data `chrome: false` (login). Only the page.
 * - `pending`: the session is not known yet. Only the page, so no frame flashes up
 *   and changes a moment later.
 */
export type ShellFrame = 'rail' | 'public' | 'bare' | 'pending';

/**
 * App frame: the chrome around the router outlet, the toasts, the update prompt and the
 * loading bar.
 *
 * There is ONE router outlet for every frame. The frame only adds or removes the chrome
 * around it, so a change of frame (sign-in, the beamer) never destroys and recreates the
 * page.
 */
@Component({
  selector: 'app-shell',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterOutlet,
    TranslatePipe,
    ToastComponent,
    SwUpdatePromptComponent,
    LoadBarComponent,
    CommandPaletteComponent,
    InboxComponent,
    NavRailComponent,
    BottomBarComponent,
    PublicHeaderComponent,
    SiteFooterComponent,
  ],
  host: { '(document:keydown)': 'onKey($event)' },
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent {
  readonly auth = inject(AuthService);
  protected readonly palette = inject(PaletteService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  /** The page fills the viewport (see `PageFrameService`): no footer, a small foot gap. */
  readonly fill = inject(PageFrameService).fill;

  /**
   * Route data `footer: true`: the footer shows at the end of the page. Only the start
   * page and the public pages have it. A work page (a list with a detail) has no footer,
   * so a page that fills the viewport ends at the bottom edge of the window.
   */
  private readonly footerRoute = signal(false);

  /** The footer shows: always in the public frame, else only where the route asks for it. */
  readonly footer = computed(() => {
    const frame = this.frame();
    if (frame === 'public') return true;
    return frame === 'rail' && this.footerRoute() && !this.fill();
  });

  /** The viewport is a phone (<= 768px): bottom bar instead of the rail. */
  readonly phone = mediaQuerySignal(MEDIA.phone);

  /** Full-width content from route data `wide`, for example the budget tab with two sidebars. */
  readonly wide = signal(false);
  /**
   * Route data `fab: true`: on a phone the page shows a floating action button above the
   * bottom bar (Aufgaben, "Neues Event"). The frame then keeps the foot of the body free
   * for it.
   */
  readonly fab = signal(false);
  /** Route data `chrome: false` turns the frame off (the login page). */
  private readonly chrome = signal(true);
  /** The first answer of `/auth/me` arrived (a principal or none). */
  private readonly sessionKnown = signal(false);

  readonly frame = computed<ShellFrame>(() => {
    if (!this.chrome()) return 'bare';
    if (!this.sessionKnown()) return 'pending';
    return this.auth.isAuthenticated() ? 'rail' : 'public';
  });

  protected onKey(event: KeyboardEvent): void {
    if (this.frame() === 'rail') this.palette.onKey(event);
  }

  constructor() {
    effect(() => {
      if (this.frame() !== 'rail') this.palette.hide();
    });

    // The app initializer starts the same request; `ensureLoaded` shares it.
    this.auth
      .ensureLoaded()
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.sessionKnown.set(true));

    // `wide`, `fab`, `footer` and `chrome` come from the route data. The deepest active route wins.
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        let r = this.route.firstChild;
        let wide = false;
        let fab = false;
        let footer = false;
        let chrome = true;
        while (r) {
          wide = r.snapshot.data['wide'] === true || wide;
          fab = r.snapshot.data['fab'] === true || fab;
          footer = r.snapshot.data['footer'] === true || footer;
          if (r.snapshot.data['chrome'] === false) chrome = false;
          r = r.firstChild;
        }
        this.wide.set(wide);
        this.fab.set(fab);
        this.footerRoute.set(footer);
        this.chrome.set(chrome);
      });
  }
}
