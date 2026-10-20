/**
 * Runs the roundtrip gate E20 (`src/app/shared/markdown/roundtrip.gate.spec.ts`). With `--write` it first rewrites
 * `roundtrip-gate.json` from the current corpus and kit; without it the spec only checks the stored decision.
 */
const { spawnSync } = require('node:child_process');

const write = process.argv.includes('--write');
const result = spawnSync(
  'npx',
  ['jest', 'src/app/shared/markdown/roundtrip.gate.spec.ts'],
  { stdio: 'inherit', env: { ...process.env, GATE_WRITE: write ? '1' : '0' } },
);
process.exit(result.status ?? 1);
