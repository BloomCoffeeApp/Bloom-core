/** Validates that every value is a finite number within [min, max]. */
export function validNumbers(values: [number, number, number][]) {
  return values.every(([v, min, max]) => Number.isFinite(v) && v >= min && v <= max)
}
