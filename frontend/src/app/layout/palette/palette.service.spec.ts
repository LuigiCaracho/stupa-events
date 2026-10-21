import { TestBed } from '@angular/core/testing';
import { PaletteService } from './palette.service';

const key = (init: KeyboardEventInit, target?: Element): KeyboardEvent => {
  const event = new KeyboardEvent('keydown', { cancelable: true, bubbles: true, ...init });
  if (target) Object.defineProperty(event, 'target', { value: target });
  return event;
};

describe('PaletteService', () => {
  const service = (): PaletteService => TestBed.inject(PaletteService);

  it('starts closed and not requested', () => {
    expect(service().isOpen()).toBe(false);
    expect(service().requested()).toBe(false);
  });

  it('shows, hides and toggles; the first show asks for the lazy component', () => {
    service().show();
    expect(service().isOpen()).toBe(true);
    expect(service().requested()).toBe(true);
    service().hide();
    expect(service().isOpen()).toBe(false);
    expect(service().requested()).toBe(true);
    service().toggle();
    expect(service().isOpen()).toBe(true);
    service().toggle();
    expect(service().isOpen()).toBe(false);
  });

  it('opens with Ctrl+K and Cmd+K, closes with the same keys, and stops the browser default', () => {
    const open = key({ key: 'k', ctrlKey: true });
    service().onKey(open);
    expect(service().isOpen()).toBe(true);
    expect(open.defaultPrevented).toBe(true);
    service().onKey(key({ key: 'K', metaKey: true }));
    expect(service().isOpen()).toBe(false);
  });

  it('ignores other keys and rich-text fields', () => {
    const plain = key({ key: 'k' });
    service().onKey(plain);
    expect(service().isOpen()).toBe(false);
    expect(plain.defaultPrevented).toBe(false);
    const editable = document.createElement('div');
    editable.setAttribute('contenteditable', 'true');
    service().onKey(key({ key: 'k', ctrlKey: true }, editable));
    expect(service().isOpen()).toBe(false);
  });
});
