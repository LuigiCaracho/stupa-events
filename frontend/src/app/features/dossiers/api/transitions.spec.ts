import {
  BOARD_MOVES,
  PRIMARY_TRANSITION,
  SYSTEM_ONLY,
  menuTransitions,
  NOTE_LABEL,
} from './transitions';
import { TRANSITION_IDS } from './event.models';
import { TRANSITION_LABEL } from './transition-label';
import { de } from '@core/i18n/translations';

describe('transition constants', () => {
  it('labels each of the 14 transitions with a German text', () => {
    expect(Object.keys(TRANSITION_LABEL).sort()).toEqual([...TRANSITION_IDS].sort());
    expect(TRANSITION_IDS).toHaveLength(14);
    for (const key of Object.values(TRANSITION_LABEL)) expect(de[key]).toBeTruthy();
  });

  it('asks for a note exactly at T03, T06, T07, T10 and T11, each with a label', () => {
    expect(Object.keys(NOTE_LABEL).sort()).toEqual(['T03', 'T06', 'T07', 'T10', 'T11']);
    for (const key of Object.values(NOTE_LABEL)) expect(de[key as keyof typeof de]).toBeTruthy();
  });

  it('keeps the drag moves to transitions of the table and never to a system step', () => {
    const ids = Object.values(BOARD_MOVES).flatMap((m) => Object.values(m));
    expect(ids.sort()).toEqual(['T01', 'T02', 'T03', 'T04', 'T06']);
    for (const id of ids) expect(SYSTEM_ONLY.has(id)).toBe(false);
  });

  it('puts the primary button on a human transition per state', () => {
    expect(PRIMARY_TRANSITION).toEqual({
      idea: 'T01',
      planning: 'T02',
      in_review: 'T04',
      approved: 'T05',
      followup: 'T09',
    });
  });

  it('leaves the primary transition and the system steps out of the menu', () => {
    expect(menuTransitions('in_review', ['T03', 'T04', 'T11'])).toEqual(['T03', 'T11']);
    expect(menuTransitions('live', ['T07', 'T08', 'T08b'])).toEqual(['T07']);
  });
});
