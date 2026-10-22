/** Spec for copying and sharing, with and without the browser APIs. */
import { TestBed } from '@angular/core/testing';
import { ShareService } from './share.service';

const DATA = { title: 'Movienight', url: 'http://localhost/e/movienight' };

function setNavigator(value: Partial<Navigator>): void {
  Object.defineProperty(window, 'navigator', { value, configurable: true });
}

describe('ShareService', () => {
  const original = window.navigator;
  afterEach(() => setNavigator(original));

  it('uses the share sheet when the browser has one', async () => {
    const share = jest.fn().mockResolvedValue(undefined);
    setNavigator({ share } as unknown as Navigator);
    expect(await TestBed.inject(ShareService).share(DATA)).toBe('shared');
    expect(share).toHaveBeenCalledWith(DATA);
  });

  it('treats a dismissed share sheet as done', async () => {
    const share = jest.fn().mockRejectedValue(new DOMException('x', 'AbortError'));
    setNavigator({ share } as unknown as Navigator);
    expect(await TestBed.inject(ShareService).share(DATA)).toBe('shared');
  });

  it('copies the link without a share sheet', async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    setNavigator({ clipboard: { writeText } } as unknown as Navigator);
    expect(await TestBed.inject(ShareService).share(DATA)).toBe('copied');
    expect(writeText).toHaveBeenCalledWith(DATA.url);
  });

  it('reports a failure when nothing works', async () => {
    setNavigator({} as Navigator);
    const service = TestBed.inject(ShareService);
    expect(await service.share(DATA)).toBe('failed');
    expect(await service.copy('x')).toBe(false);
  });
});
