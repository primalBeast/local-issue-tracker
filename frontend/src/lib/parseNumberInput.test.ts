import { describe, expect, it } from 'vitest';
import { parseNumberInput } from './parseNumberInput';

describe('parseNumberInput', () => {
  it('clears a blank field to null', () => {
    expect(parseNumberInput('')).toBeNull();
    expect(parseNumberInput('  ')).toBeNull();
    expect(parseNumberInput('\t')).toBeNull();
  });

  it('parses finite numbers, including 0', () => {
    expect(parseNumberInput('3')).toBe(3);
    expect(parseNumberInput('0')).toBe(0);
    expect(parseNumberInput('  12 ')).toBe(12);
  });

  it('leaves invalid text unchanged', () => {
    // undefined means do not write; the stored rank stays as it was.
    expect(parseNumberInput('abc')).toBeUndefined();
    expect(parseNumberInput('NaN')).toBeUndefined();
    expect(parseNumberInput('1e')).toBeUndefined();
  });

  it('rejects numbers outside min and max without turning them into null', () => {
    expect(parseNumberInput('2', { min: 3, max: 9 })).toBeUndefined();
    expect(parseNumberInput('10', { min: 3, max: 9 })).toBeUndefined();
    expect(parseNumberInput('3', { min: 3, max: 9 })).toBe(3);
    expect(parseNumberInput('', { min: 3 })).toBeNull();
  });
});
