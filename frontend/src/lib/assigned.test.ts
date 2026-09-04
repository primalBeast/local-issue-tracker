import { describe, expect, it } from 'vitest';
import { isAssignedField, nameAlreadyListed } from './assigned';

describe('isAssignedField', () => {
  it('matches the two Assigned fields', () => {
    expect(isAssignedField('dn_assigned_to')).toBe(true);
    expect(isAssignedField('customer_assigned_to')).toBe(true);
    expect(isAssignedField('waiting_for')).toBe(false);
  });
});

describe('nameAlreadyListed', () => {
  it('treats trim and case as the same name', () => {
    expect(nameAlreadyListed(['Ann', 'Mia'], 'ann')).toBe(true);
    expect(nameAlreadyListed(['Ann'], '  Ann  ')).toBe(true);
    expect(nameAlreadyListed(['Ann'], 'Bob')).toBe(false);
    expect(nameAlreadyListed(['Ann'], '   ')).toBe(false);
    expect(nameAlreadyListed(undefined, 'Ann')).toBe(false);
  });
});
