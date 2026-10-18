import { controlFor, focusField } from './focus-field';

describe('focus field', () => {
  it('maps fix actions and fields to the form control', () => {
    expect(controlFor('change_date', null)).toBe('startDate');
    expect(controlFor('set_end', null)).toBe('endDate');
    expect(controlFor('pick_venue', 'venue_text')).toBe('venueId');
    expect(controlFor('mark_cancellation', null)).toBe('title');
    expect(controlFor('fill_field', 'ends_at')).toBe('endDate');
    expect(controlFor('fill_field', 'primary_category_id')).toBe('primaryCategoryId');
    expect(controlFor('fill_field', 'organizationId')).toBe('title');
    expect(controlFor('fill_field', null)).toBe('title');
  });

  it('focuses the first control of the field and reports a miss', () => {
    const root = document.createElement('div');
    root.innerHTML = '<app-input formcontrolname="summary"><input id="s"></app-input>';
    document.body.append(root);
    expect(focusField(root, 'fill_field', 'summary')).toBe(true);
    expect(document.activeElement?.id).toBe('s');
    expect(focusField(root, 'fill_field', 'title')).toBe(false);
    root.remove();
  });
});
