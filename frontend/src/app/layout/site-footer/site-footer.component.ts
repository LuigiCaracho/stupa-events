/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/site-footer/site-footer.component.ts */
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';

/**
 * The footer of the public frame and of the start page. M1 shows the co-branding line
 * only; the configurable Impressum and Datenschutz links return with the public site.
 */
@Component({
  selector: 'app-site-footer',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe],
  templateUrl: './site-footer.component.html',
  styleUrl: './site-footer.component.scss',
})
export class SiteFooterComponent {}
