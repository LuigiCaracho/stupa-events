/** Copied from STUPA-Workflow@93c33d6 frontend/jest.config.js */
module.exports = {
  preset: 'jest-preset-angular',
  setupFilesAfterEnv: ['<rootDir>/setup-jest.ts'],
  testEnvironment: 'jsdom',
  // Jest 30 and jsdom 26 need much more RAM per worker (#jest30). Without a cap, the full
  // suite exhausts the memory on machines with many cores (OOM). Use half of the cores and
  // restart a worker above 1 GB of idle RSS.
  maxWorkers: '50%',
  workerIdleMemoryLimit: '1GB',
  roots: ['<rootDir>/src'],
  testMatch: ['**/*.spec.ts'],
  moduleNameMapper: {
    '^@core/(.*)$': '<rootDir>/src/app/core/$1',
    '^@shared/(.*)$': '<rootDir>/src/app/shared/$1',
    '^@stupa-makers/ui-kit/markdown-editor$':
      '<rootDir>/vendor/ui-kit/markdown-editor/src/public-api.ts',
    '^@stupa-makers/ui-kit$': '<rootDir>/vendor/ui-kit/src/public-api.ts',
    '\\.(css|scss)$': '<rootDir>/src/testing/style-mock.js',
  },
  transform: {
    '^.+\\.(ts|mjs|js|html)$': [
      'jest-preset-angular',
      {
        tsconfig: '<rootDir>/tsconfig.spec.json',
        stringifyContentPathRegex: '\\.(html|svg)$',
      },
    ],
  },
  transformIgnorePatterns: ['node_modules/(?!.*\\.mjs$|@angular|rxjs)'],
  collectCoverageFrom: [
    'src/app/**/*.ts',
    '!src/app/**/*.spec.ts',
    '!src/app/**/index.ts',
    // Bootstrap and wiring files (composition root). The build and the E2E tests cover them.
    '!src/app/app.config.ts',
    '!src/app/app.routes.ts',
  ],
  // M1 gate, just below the measured values (98.8/96.4/98.2/99.4). Feature pages add specs;
  // keep or raise the numbers (workflow tool: 98/96/98/99).
  coverageThreshold: {
    global: { statements: 97, branches: 94, functions: 97, lines: 98 },
  },
};
