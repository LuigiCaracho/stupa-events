/** Account page (`/konto`): who is signed in, which roles and organizations the groups grant, and logout. */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { ButtonComponent, CardComponent } from '@stupa-makers/ui-kit';

@Component({
  selector: 'app-account',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, CardComponent, PageHeaderComponent],
  templateUrl: './account.component.html',
  styleUrl: './account.component.scss',
})
export class AccountComponent {
  readonly auth = inject(AuthService);
}
