/** Public landing page (`/`, frame `public`): what the platform is and the way to the login. */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent } from '@stupa-makers/ui-kit';

@Component({
  selector: 'app-home',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent],
  template: `
    <section class="home">
      <h1>{{ 'home.heading' | t }}</h1>
      <p>{{ 'home.body' | t }}</p>
      <app-button variant="fill" size="lg" (click)="auth.login()">{{ 'login.button' | t }}</app-button>
    </section>
  `,
  styles: `
    .home {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: var(--space-4);
      max-width: 40rem;
    }
    h1,
    p {
      margin: 0;
    }
  `,
})
export class HomeComponent {
  readonly auth = inject(AuthService);
}
