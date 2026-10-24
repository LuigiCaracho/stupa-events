/** Spec for the ALTCHA solver: the proof of work, a fresh challenge per call, ALTCHA off (404) and an unsolvable challenge. */
import { createHash, webcrypto } from 'node:crypto';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AltchaService, type AltchaChallenge, solveChallenge } from './altcha.service';

const URL = '/api/public/altcha/challenge';

function challengeFor(number: number, maxnumber = 10): AltchaChallenge {
  const salt = 'abc?expires=9999999999';
  const challenge = createHash('sha256').update(`${salt}${number}`).digest('hex');
  return { algorithm: 'SHA-256', challenge, salt, signature: 'sig', maxnumber };
}

describe('AltchaService', () => {
  let http: HttpTestingController;
  let service: AltchaService;

  beforeAll(() => {
    if (!globalThis.crypto?.subtle) {
      Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
    }
  });
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    service = TestBed.inject(AltchaService);
  });
  afterEach(() => http.verify());

  const solving = async (answer: (r: ReturnType<HttpTestingController['expectOne']>) => void) => {
    const result = service.solve();
    await Promise.resolve();
    answer(http.expectOne(URL));
    return result;
  };

  it('solves a fresh challenge into the base64 payload', async () => {
    const c = challengeFor(3);
    const solution = await solving((r) => r.flush(c));
    expect(JSON.parse(atob(solution as string))).toEqual({
      algorithm: 'SHA-256',
      challenge: c.challenge,
      number: 3,
      salt: c.salt,
      signature: 'sig',
    });
  });

  it('asks for a new challenge on every call', async () => {
    await solving((r) => r.flush(challengeFor(1)));
    await solving((r) => r.flush(challengeFor(2)));
  });

  it('gives null when the server has ALTCHA off', async () => {
    await expect(
      solving((r) => r.flush(null, { status: 404, statusText: 'Not Found' })),
    ).resolves.toBeNull();
  });

  it('rejects when the request fails', async () => {
    await expect(
      solving((r) => r.flush(null, { status: 500, statusText: 'x' })),
    ).rejects.toBeDefined();
  });

  it('rejects a challenge without a solution up to maxnumber', async () => {
    await expect(solveChallenge(challengeFor(5, 2))).rejects.toThrow(/unsolvable/);
  });
});
