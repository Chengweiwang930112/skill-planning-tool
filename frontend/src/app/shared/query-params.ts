/** A query parameter that may be repeated, as the router hands it over: absent, once or more. */
export function toList(value: unknown): string[] {
  return value == null ? [] : Array.isArray(value) ? value : [String(value)];
}
