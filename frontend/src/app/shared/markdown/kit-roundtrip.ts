/**
 * Roundtrip through the real Tiptap editor of the ui-kit (E20): the text goes in as the editor content and comes out
 * through the same serializer that `valueChange` uses. The kit keeps both the editor and the serializer private, so
 * this file is the one place that reaches in; the gate test and the runtime check of the editor shell share it.
 */
import type { MarkdownEditorComponent } from '@stupa-makers/ui-kit/markdown-editor';

interface EditorInternals {
  editor: { storage: Record<string, { getMarkdown?: () => string }> } | null;
}

/** The Markdown that the mounted editor would emit for its current content, or null when it is not mounted. */
export function exportedMarkdown(component: MarkdownEditorComponent): string | null {
  const editor = (component as unknown as EditorInternals).editor;
  return editor?.storage['markdown']?.getMarkdown?.() ?? null;
}

/** True when the editor, given `source`, would write back exactly `source`. */
export function roundtripsExactly(component: MarkdownEditorComponent, source: string): boolean {
  return exportedMarkdown(component) === source;
}
