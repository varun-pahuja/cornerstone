/** Minimal class-name joiner (no extra dependencies). */
export const cn = (...classes: (string | false | null | undefined)[]): string =>
  classes.filter(Boolean).join(" ");

/** Format an optional number with a unit; absent values are honestly "Unavailable". */
export const fmt = (v: number | null | undefined, unit = ""): string =>
  v === null || v === undefined ? "Unavailable" : `${v}${unit}`;
