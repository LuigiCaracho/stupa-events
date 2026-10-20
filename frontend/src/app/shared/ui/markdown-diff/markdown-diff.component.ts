/**
 * Line diff of two document revisions (`GET /documents/{id}/diff`). Pattern from the workflow tool's config diff: plain
 * text only, line numbers on both sides, and every changed line carries a sign and a hidden word, so colour is never
 * the only signal.
 */
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { DiffOut } from '../../../features/dossiers/model/document.models';

const SIGN = { equal: ' ', add: '+', remove: '−' } as const;
const WORD = { equal: 'diff.equal', add: 'diff.added', remove: 'diff.removed' } as const;

@Component({
  selector: 'app-markdown-diff',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe],
  templateUrl: './markdown-diff.component.html',
  styleUrl: './markdown-diff.component.scss',
})
export class MarkdownDiffComponent {
  readonly diff = input.required<DiffOut>();

  protected readonly rows = computed(() =>
    this.diff().lines.map((line) => ({
      ...line,
      sign: SIGN[line.op],
      wordKey: WORD[line.op],
    })),
  );
}
