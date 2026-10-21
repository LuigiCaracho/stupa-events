import { isPaletteShortcut } from './shortcut';

const key = (init: KeyboardEventInit, target?: Element): KeyboardEvent => {
  const event = new KeyboardEvent('keydown', { cancelable: true, bubbles: true, ...init });
  if (target) Object.defineProperty(event, 'target', { value: target });
  return event;
};

describe('isPaletteShortcut', () => {
  it('matches Ctrl+K and Cmd+K in either case', () => {
    expect(isPaletteShortcut(key({ key: 'k', ctrlKey: true }))).toBe(true);
    expect(isPaletteShortcut(key({ key: 'K', metaKey: true }))).toBe(true);
  });

  it('ignores other keys and extra modifiers', () => {
    expect(isPaletteShortcut(key({ key: 'k' }))).toBe(false);
    expect(isPaletteShortcut(key({ key: 'j', ctrlKey: true }))).toBe(false);
    expect(isPaletteShortcut(key({ key: 'k', ctrlKey: true, shiftKey: true }))).toBe(false);
    expect(isPaletteShortcut(key({ key: 'k', ctrlKey: true, altKey: true }))).toBe(false);
  });

  it('leaves the combination to a rich-text editor and a handled event', () => {
    const editable = document.createElement('div');
    editable.setAttribute('contenteditable', 'true');
    expect(isPaletteShortcut(key({ key: 'k', ctrlKey: true }, editable))).toBe(false);
    const handled = key({ key: 'k', ctrlKey: true });
    handled.preventDefault();
    expect(isPaletteShortcut(handled)).toBe(false);
  });

  it('works inside an ordinary text field', () => {
    expect(
      isPaletteShortcut(key({ key: 'k', ctrlKey: true }, document.createElement('textarea'))),
    ).toBe(true);
  });
});
