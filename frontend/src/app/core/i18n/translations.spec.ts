/** Catalog sanity checks. */
import { de } from './translations';

describe('translations', () => {
  it('has no empty string', () => {
    expect(Object.entries(de).filter(([, v]) => v.trim() === '')).toEqual([]);
  });

  it('uses the Du-form and no Sie-form in the shell strings', () => {
    expect(Object.values(de).filter((v) => /\bSie\b/.test(v))).toEqual([]);
  });

  it('gendered with the colon or neutral, never with star, underscore, slash or capital I', () => {
    const forms = /\*in|_in|\/in\b|[a-zäöüß]In(nen)?\b|\*innen|\(in\)/;
    expect(Object.entries(de).filter(([, v]) => forms.test(v))).toEqual([]);
  });

  it('keeps every guard code and fix action of the contract translated', () => {
    const codes = [
      'field_missing',
      'venue_missing',
      'start_in_past',
      'image_required',
      'rights_incomplete',
      'attachment_quarantined',
      'duplicate_unresolved',
      'title_has_status',
      'open_comment_on_hero',
      'flyer_date',
      'location_unconfirmed',
      'facts_invalid',
      'checklist_open',
      'open_comment_required',
      'publish_at_not_reached',
      'not_human_approved',
      'not_ended_yet',
      'origin_kind_mismatch',
      'retrospective_missing',
      'outcome_missing',
      'howto_unverified',
      'followup_not_due',
      'four_eyes',
      'time_ambiguous',
      'time_gap',
      'end_estimated',
      'long_running',
    ];
    const fixes = [
      'fill_field',
      'change_date',
      'upload_poster',
      'pick_venue',
      'fill_rights',
      'review_duplicate',
      'mark_cancellation',
      'open_comment',
      'confirm_flyer',
      'confirm_location',
      'fill_facts',
      'open_checklist',
      'confirm_time',
      'set_end',
      'make_offer',
      'fill_retrospective',
      'fill_outcome',
      'verify_howto',
    ];
    const missing = [...codes.map((c) => `guards.${c}`), ...fixes.map((f) => `fix.${f}`)].filter(
      (k) => !(k in de),
    );
    expect(missing).toEqual([]);
    expect(fixes).toHaveLength(18);
  });

  // TODO Stufe B: en catalog and the parity spec (every de key exists in en).
  it.todo('has an en entry for every de key');
});
