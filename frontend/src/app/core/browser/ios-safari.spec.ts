import { isIosSafari } from './ios-safari';

const SAFARI_IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
const CHROME_IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0 Mobile/15E148 Safari/604.1';
const MAC_SAFARI =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15';

describe('isIosSafari', () => {
  it('accepts Safari on an iPhone', () => {
    expect(isIosSafari({ userAgent: SAFARI_IPHONE })).toBe(true);
  });

  it('accepts an iPad that reports itself as a Mac with a touch screen', () => {
    expect(isIosSafari({ userAgent: MAC_SAFARI, platform: 'MacIntel', maxTouchPoints: 5 })).toBe(
      true,
    );
  });

  it('refuses a real Mac', () => {
    expect(isIosSafari({ userAgent: MAC_SAFARI, platform: 'MacIntel', maxTouchPoints: 0 })).toBe(
      false,
    );
  });

  it('refuses Chrome, Firefox and Edge on iOS, which have no install entry in the share sheet', () => {
    expect(isIosSafari({ userAgent: CHROME_IPHONE })).toBe(false);
    expect(isIosSafari({ userAgent: SAFARI_IPHONE.replace('Version/18.0', 'FxiOS/130') })).toBe(
      false,
    );
    expect(isIosSafari({ userAgent: SAFARI_IPHONE.replace('Version/18.0', 'EdgiOS/130') })).toBe(
      false,
    );
  });

  it('refuses Android', () => {
    expect(
      isIosSafari({ userAgent: 'Mozilla/5.0 (Linux; Android 14) Chrome/130 Mobile Safari/537.36' }),
    ).toBe(false);
  });
});
