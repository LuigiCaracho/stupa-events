/** Spec for the subscription links. */
import { ALL_ICS, anchoredCategory, categoryIcs, subscribeLinks } from './subscribe-links';

describe('subscribeLinks', () => {
  it('turns the https URL into a webcal URL on the same host', () => {
    expect(subscribeLinks('https://events.example', ALL_ICS)).toEqual({
      https: 'https://events.example/ics/all.ics',
      webcal: 'webcal://events.example/ics/all.ics',
    });
  });

  it('keeps the port of a local stack', () => {
    expect(subscribeLinks('http://localhost:8081', categoryIcs('party')).webcal).toBe(
      'webcal://localhost:8081/ics/k/party.ics',
    );
  });
});

describe('anchoredCategory', () => {
  it('reads the slug of the anchor and refuses anything else', () => {
    expect(anchoredCategory('k=party')).toBe('party');
    expect(anchoredCategory('k=<script>')).toBeNull();
    expect(anchoredCategory(null)).toBeNull();
  });
});
