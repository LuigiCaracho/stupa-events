import { groupOf, isImageFile, isRestricted, visibilityOptions } from './attachment-kinds';

describe('attachment kinds', () => {
  it('never offers "Alle Mitglieder" for offers, business plans and contracts', () => {
    for (const kind of ['quote', 'business_plan', 'contract'] as const) {
      expect(isRestricted(kind)).toBe(true);
      expect(visibilityOptions(kind)).toEqual(['team', 'org']);
    }
    expect(isRestricted('other')).toBe(false);
    expect(visibilityOptions('social_post')).toEqual(['team', 'org', 'shared']);
  });

  it('puts every kind into a group', () => {
    expect(groupOf('poster')).toBe('poster');
    expect(groupOf('contract')).toBe('documents');
    expect(groupOf('quote')).toBe('quotes');
    expect(groupOf('howto_file')).toBe('other');
  });

  it('recognises images by their type', () => {
    expect(isImageFile(new File([''], 'a.png', { type: 'image/png' }))).toBe(true);
    expect(isImageFile(new File([''], 'a.pdf', { type: 'application/pdf' }))).toBe(false);
  });
});
