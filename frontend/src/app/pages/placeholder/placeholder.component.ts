/**
 * Stand-in for a feature route that the feature builder has not wired yet
 * (`app/feature-routes.ts`). It disappears when the route points at `features/**`.
 */
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';

@Component({
  selector: 'app-placeholder',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, EmptyStateComponent],
  template: `<app-empty-state plain level="1" [heading]="'placeholder.heading' | t" [body]="'placeholder.body' | t" />`,
})
export class PlaceholderComponent {}
