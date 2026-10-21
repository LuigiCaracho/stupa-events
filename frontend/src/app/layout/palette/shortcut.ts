/**
 * The key combination of the palette: Strg+K, on macOS Cmd+K (M5 contract 11.5). It stays out of the way of rich-text
 * fields, which use the same keys for a link; plain inputs and text areas do not, so the palette opens there too.
 */
export function isPaletteShortcut(event: KeyboardEvent): boolean {
  if (event.defaultPrevented || event.altKey || event.shiftKey) return false;
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'k') return false;
  const target = event.target;
  return !(target instanceof Element && target.closest('[contenteditable="true"], .ProseMirror'));
}
