/** Login page (I01, `/login`, frame `bare`): one button to the IdP and a link to the public page. */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, CardComponent } from '@stupa-makers/ui-kit';

@Component({
  selector: 'app-login',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, CardComponent, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  readonly auth = inject(AuthService);
  readonly mark = 'assets/logos/stupa-mark.svg';
}
