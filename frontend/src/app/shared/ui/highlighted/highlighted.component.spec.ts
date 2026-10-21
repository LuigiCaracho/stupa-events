import { render } from '@testing-library/angular';
import { HighlightedComponent } from './highlighted.component';

describe('HighlightedComponent', () => {
  it('draws hits as mark elements', async () => {
    const { container } = await render(HighlightedComponent, {
      inputs: {
        segments: [
          { text: 'Fach', hit: false },
          { text: 'schaft', hit: true },
        ],
      },
    });
    expect(container.querySelectorAll('mark')).toHaveLength(1);
    expect(container.textContent).toBe('Fachschaft');
  });

  it('never turns text into markup', async () => {
    const { container } = await render(HighlightedComponent, {
      inputs: { segments: [{ text: '<img src=x onerror=alert(1)>', hit: true }] },
    });
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('mark')?.textContent).toBe('<img src=x onerror=alert(1)>');
  });
});
