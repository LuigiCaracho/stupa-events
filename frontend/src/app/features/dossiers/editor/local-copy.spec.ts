import { clearLocalCopy, readLocalCopy, writeLocalCopy } from './local-copy';

describe('local copy', () => {
  afterEach(() => {
    jest.restoreAllMocks();
    localStorage.clear();
  });

  it('writes, reads and clears', () => {
    writeLocalCopy('a', 'text');
    expect(readLocalCopy('a')).toBe('text');
    clearLocalCopy('a');
    expect(readLocalCopy('a')).toBeNull();
  });

  it('survives blocked storage', () => {
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    jest.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(readLocalCopy('a')).toBeNull();
    expect(() => writeLocalCopy('a', 'x')).not.toThrow();
    expect(() => clearLocalCopy('a')).not.toThrow();
  });
});
