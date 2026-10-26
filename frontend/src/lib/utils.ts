/** Minimal class-name joiner (no extra dependencies). */
export const cn = (...classes: (string | false | null | undefined)[]): string =>
  classes.filter(Boolean).join(" ");
