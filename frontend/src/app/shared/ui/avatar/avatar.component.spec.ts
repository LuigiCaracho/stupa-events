/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/shared/ui/avatar/avatar.component.spec.ts (adapted) */
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../testing/a11y';
import { AvatarComponent, initials } from './avatar.component';

describe('initials', () => {
  it.each([
    ['Mara Keller', 'MK'],
    ['Paul', 'P'],
    ['Anna-Lena von Stein', 'AS'],
    ['  jonas   weber ', 'JW'],
    ['Erika Beispiel (erika@example.org)', 'EB'],
    ['"Öztürk" Ümit', 'ÖÜ'],
    ['', '?'],
    ['()', '?'],
  ])('%s gives %s', (name, letters) => {
    expect(initials(name)).toBe(letters);
  });
});

describe('AvatarComponent', () => {
  it('shows the initials and names the person', async () => {
    const { container } = await render(AvatarComponent, { inputs: { name: 'Mara Keller' } });
    const img = screen.getByRole('img', { name: 'Mara Keller' });
    expect(img).toHaveTextContent('MK');
    expect(img).toHaveAttribute('title', 'Mara Keller');
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('hides itself from screen readers when it is decorative', async () => {
    const view = await render(AvatarComponent, {
      inputs: { name: 'Mara Keller', decorative: true },
    });
    const host = view.fixture.nativeElement as HTMLElement;
    expect(screen.queryByRole('img')).toBeNull();
    expect(host).toHaveAttribute('aria-hidden', 'true');
  });

  it('carries the size and accent classes', async () => {
    const view = await render(AvatarComponent, {
      inputs: { name: 'Mara Keller', size: 'sm', accent: true },
    });
    const host = view.fixture.nativeElement as HTMLElement;
    expect(host).toHaveClass('av--sm');
    expect(host).toHaveClass('av--accent');
  });

  it('carries the extra small class', async () => {
    const view = await render(AvatarComponent, { inputs: { name: 'Mara Keller', size: 'xs' } });
    const host = view.fixture.nativeElement as HTMLElement;
    expect(host).toHaveClass('av--xs');
    expect(host).not.toHaveClass('av--sm');
  });
});
