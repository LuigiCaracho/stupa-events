/** Tells iOS Safari from other browsers: only there an app is installed by hand through the share sheet (B4). */

export interface NavigatorLike {
  userAgent: string;
  platform?: string;
  maxTouchPoints?: number;
}

const OTHER_IOS_BROWSERS = /CriOS|FxiOS|EdgiOS|OPiOS|GSA\//;

/** iPhone, iPad (also the desktop-class iPadOS that calls itself a Mac) and iPod, without Chrome, Firefox, Edge or Opera on iOS. */
export function isIosSafari(nav: NavigatorLike): boolean {
  const ios =
    /iPhone|iPad|iPod/.test(nav.userAgent) ||
    (nav.platform === 'MacIntel' && (nav.maxTouchPoints ?? 0) > 1);
  return ios && !OTHER_IOS_BROWSERS.test(nav.userAgent);
}
