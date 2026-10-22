/** Spec for the poster box: size from the API, lazy by default, placeholder without an image or after an error. */
import { render } from '@testing-library/angular';
import { EventPosterComponent } from './event-poster.component';

const IMAGE = { url: '/api/public/media/a.webp', width: 1200, height: 630 };

describe('EventPosterComponent', () => {
  it('renders the image with width, height, alt and lazy loading', async () => {
    const { container } = await render(EventPosterComponent, {
      inputs: { image: IMAGE, alt: 'Plakat' },
    });
    const img = container.querySelector('img') as HTMLImageElement;
    expect(img).toHaveAttribute('width', '1200');
    expect(img).toHaveAttribute('height', '630');
    expect(img).toHaveAttribute('alt', 'Plakat');
    expect(img).toHaveAttribute('loading', 'lazy');
    expect(img).not.toHaveAttribute('fetchpriority');
  });

  it('loads an image above the fold at once with high priority', async () => {
    const { container } = await render(EventPosterComponent, {
      inputs: { image: IMAGE, eager: true },
    });
    const img = container.querySelector('img') as HTMLImageElement;
    expect(img).not.toHaveAttribute('loading');
    expect(img).toHaveAttribute('fetchpriority', 'high');
  });

  it('is decorative (empty alt) when the API gives no alt text', async () => {
    const { container } = await render(EventPosterComponent, { inputs: { image: IMAGE } });
    expect(container.querySelector('img')).toHaveAttribute('alt', '');
  });

  it('shows a placeholder without an image', async () => {
    const none = await render(EventPosterComponent);
    expect(none.container.querySelector('img')).toBeNull();
    expect(none.container.querySelector('.poster__ph')).not.toBeNull();
  });

  it('falls back to the placeholder after a load error', async () => {
    const failing = await render(EventPosterComponent, { inputs: { image: IMAGE } });
    failing.container.querySelector('img')?.dispatchEvent(new Event('error'));
    failing.fixture.detectChanges();
    expect(failing.container.querySelector('img')).toBeNull();
    expect(failing.container.querySelector('.poster__ph')).not.toBeNull();
  });
});
