/**
 * Roundtrip gate E20 (contract M4 section 7): every corpus file, mounted in the kit's Tiptap editor, must come back
 * byte for byte. The run writes `roundtrip-gate.json` with `npm run gate:roundtrip`; this spec fails when the stored
 * decision no longer matches the corpus or the kit commit.
 */
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { TestBed } from '@angular/core/testing';
import { MarkdownEditorComponent } from '@stupa-makers/ui-kit/markdown-editor';
import { exportedMarkdown } from './kit-roundtrip';

const CORPUS = join(__dirname, '../../../../tests/fixtures/markdown');
const DECISION = join(__dirname, 'roundtrip-gate.json');
const KIT_SRC = join(__dirname, '../../../../vendor/ui-kit/markdown-editor/src');

const files = readdirSync(CORPUS)
  .filter((f) => f.endsWith('.md'))
  .sort();

function corpusHash(): string {
  const hash = createHash('sha256');
  files.forEach((f) => hash.update(f).update(readFileSync(join(CORPUS, f))));
  return hash.digest('hex').slice(0, 16);
}

function kitCommit(): string {
  const hash = createHash('sha256');
  readdirSync(KIT_SRC)
    .filter((f) => f.endsWith('.ts') && !f.endsWith('.spec.ts'))
    .sort()
    .forEach((f) => hash.update(f).update(readFileSync(join(KIT_SRC, f))));
  return hash.digest('hex').slice(0, 16);
}

function roundtrip(source: string): string | null {
  const fixture = TestBed.createComponent(MarkdownEditorComponent);
  fixture.componentRef.setInput('value', source);
  fixture.detectChanges();
  const out = exportedMarkdown(fixture.componentInstance);
  fixture.destroy();
  return out;
}

describe('markdown roundtrip gate (E20)', () => {
  it('has a corpus of at least 15 files', () => {
    expect(files.length).toBeGreaterThanOrEqual(15);
  });

  it('matches the decision file', () => {
    const failed = files.filter((f) => {
      const text = readFileSync(join(CORPUS, f));
      const out = roundtrip(text.toString('utf8'));
      return out === null || Buffer.compare(Buffer.from(out, 'utf8'), text) !== 0;
    });
    const current = {
      passed: failed.length === 0,
      failed,
      corpusHash: corpusHash(),
      kitCommit: kitCommit(),
    };
    if (process.env['GATE_WRITE'] === '1') {
      writeFileSync(DECISION, `${JSON.stringify(current, null, 2)}\n`);
    }
    expect(JSON.parse(readFileSync(DECISION, 'utf8'))).toEqual(current);
  });
});
