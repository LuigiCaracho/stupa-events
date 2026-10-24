/**
 * Copied from STUPA-Workflow@93c33d6 frontend/src/app/features/apply/altcha.service.ts (adapted: own challenge
 * route, plain HttpClient). ALTCHA proof of work for the public forms: `solve` fetches a server-signed challenge
 * from `/api/public/altcha/challenge` and solves it locally with Web Crypto (find `number` with
 * `SHA-256(salt + number) == challenge`), so no third-party script and no external request is involved. A
 * solution is good for one request only; every request that needs one calls `solve` again.
 */
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { firstValueFrom } from 'rxjs';

export interface AltchaChallenge {
  algorithm: string;
  challenge: string;
  salt: string;
  signature: string;
  maxnumber: number;
}

async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}

export async function solveChallenge(c: AltchaChallenge): Promise<string> {
  for (let number = 0; number <= c.maxnumber; number++) {
    if ((await sha256Hex(`${c.salt}${number}`)) === c.challenge) {
      const { algorithm, challenge, salt, signature } = c;
      return btoa(JSON.stringify({ algorithm, challenge, number, salt, signature }));
    }
  }
  throw new Error('altcha challenge unsolvable within maxnumber');
}

@Injectable({ providedIn: 'root' })
export class AltchaService {
  private readonly http = inject(HttpClient);
  private readonly url = `${inject(API_BASE_URL)}/public/altcha/challenge`;

  /** The base64 solution of a fresh challenge, or `null` when the server has ALTCHA off (404). Rejects on any other failure. */
  async solve(): Promise<string | null> {
    try {
      const challenge = await firstValueFrom(
        this.http.get<AltchaChallenge>(this.url, { withCredentials: false }),
      );
      return await solveChallenge(challenge);
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 404) return null;
      throw err;
    }
  }
}
