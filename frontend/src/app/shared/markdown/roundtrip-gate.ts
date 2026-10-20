/**
 * Result of the roundtrip gate E20 as the editor shell reads it: when every corpus file survives Tiptap byte for
 * byte, the rich editor is the default mode; otherwise the Markdown source is, and the editor stays an option.
 */
import gate from './roundtrip-gate.json';

export const RICH_EDITOR_DEFAULT: boolean = gate.passed;
export const ROUNDTRIP_FAILED: readonly string[] = gate.failed;
