import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Component } from '@angular/core';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { TextareaComponent } from './textarea.component';

@Component({
  standalone: true,
  imports: [ReactiveFormsModule, TextareaComponent],
  template: `<app-textarea
    [formControl]="control"
    label="Beschreibung"
    hint="Markdown"
    [error]="error"
    [required]="true"
  />`,
})
class HostComponent {
  readonly control = new FormControl('Start');
  error = '';
}

describe('TextareaComponent', () => {
  it('writes the form value in and the typed text out', async () => {
    const view = await render(HostComponent);
    const field = screen.getByLabelText('Beschreibung');
    expect(field).toHaveValue('Start');
    await userEvent.type(field, ' mehr');
    expect(view.fixture.componentInstance.control.value).toBe('Start mehr');
    view.fixture.componentInstance.control.setValue(null);
    view.fixture.detectChanges();
    expect(field).toHaveValue('');
  });

  it('describes the field with the hint, then with the error', async () => {
    const view = await render(HostComponent);
    const field = screen.getByLabelText('Beschreibung');
    expect(field).toHaveAccessibleDescription('Markdown');
    view.fixture.componentInstance.error = 'Zu kurz';
    view.fixture.componentRef.changeDetectorRef.markForCheck();
    view.fixture.detectChanges();
    expect(screen.getByRole('alert')).toHaveTextContent('Zu kurz');
    expect(field).toHaveAttribute('aria-invalid', 'true');
  });

  it('can be disabled by the form and has no axe violations', async () => {
    const view = await render(HostComponent);
    view.fixture.componentInstance.control.disable();
    view.fixture.detectChanges();
    expect(screen.getByLabelText('Beschreibung')).toBeDisabled();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('marks itself touched on blur', async () => {
    const view = await render(HostComponent);
    await userEvent.click(screen.getByLabelText('Beschreibung'));
    await userEvent.tab();
    expect(view.fixture.componentInstance.control.touched).toBe(true);
  });
});
