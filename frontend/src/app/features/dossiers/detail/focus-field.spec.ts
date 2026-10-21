import { controlFor, focusField } from './focus-field';

describe('focus field', () => {
  it('maps the field of a hint to the form control', () => {
    expect(controlFor('starts_at')).toBe('startDate');
    expect(controlFor('endsAt')).toBe('endDate');
    expect(controlFor('venue')).toBe('venueId');
    expect(controlFor('category')).toBe('primaryCategoryId');
    expect(controlFor('primary_category_id')).toBe('primaryCategoryId');
    expect(controlFor('summary')).toBe('summary');
    expect(controlFor(null)).toBe('title');
  });

  it('focuses the first control of the field and reports a miss', () => {
    const root = document.createElement('div');
    root.innerHTML = '<app-input formcontrolname="summary"><input id="s"></app-input>';
    document.body.append(root);
    expect(focusField(root, 'summary')).toBe(true);
    expect(document.activeElement?.id).toBe('s');
    expect(focusField(root, 'title')).toBe(false);
    root.remove();
  });
});
