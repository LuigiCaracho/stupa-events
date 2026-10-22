/**
 * A link that looks like a kit button: `<a appLinkButton="tonal" routerLink="/abos">`. The kit button is a native
 * `<button>`, which is wrong for navigation, downloads, `webcal:` and external targets; this keeps the same tokens
 * on an anchor (44 px high on a phone for the touch target).
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import type { ButtonLook } from '@stupa-makers/ui-kit';

@Component({
  // eslint-disable-next-line @angular-eslint/component-selector -- an anchor that carries the button look
  selector: 'a[appLinkButton]',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'lb', '[class]': "'lb lb--' + look() + ' lb--' + size()" },
  template: '<ng-content />',
  styleUrl: './link-button.component.scss',
})
export class LinkButtonComponent {
  readonly look = input<Extract<ButtonLook, 'fill' | 'tonal' | 'outlined' | 'text'>>('tonal', {
    alias: 'appLinkButton',
  });
  readonly size = input<'md' | 'lg'>('md');
}
