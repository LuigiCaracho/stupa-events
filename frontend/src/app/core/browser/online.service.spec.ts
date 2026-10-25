import { TestBed } from '@angular/core/testing';
import { OnlineService } from './online.service';

describe('OnlineService', () => {
  afterEach(() => jest.restoreAllMocks());

  it('starts with navigator.onLine and follows the window events', () => {
    jest.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(true);
    const online = TestBed.inject(OnlineService);
    expect(online.online()).toBe(true);
    window.dispatchEvent(new Event('offline'));
    expect(online.online()).toBe(false);
    window.dispatchEvent(new Event('online'));
    expect(online.online()).toBe(true);
  });

  it('starts offline when the browser says so and stops listening on destroy', () => {
    jest.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false);
    const online = TestBed.inject(OnlineService);
    expect(online.online()).toBe(false);
    TestBed.resetTestingModule();
    window.dispatchEvent(new Event('online'));
    expect(online.online()).toBe(false);
  });
});
