import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../services/api";

export type Load<T> = { data: T | null; error: string | null; loading: boolean };

/**
 * Poll a fetcher on an interval. On error the last good data is kept and the
 * error is surfaced — stale-but-labeled beats a blank screen.
 */
export function usePoll<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  deps: readonly unknown[] = [],
): Load<T> & { refresh: () => void } {
  const [state, setState] = useState<Load<T>>({ data: null, error: null, loading: true });

  const load = useCallback(async () => {
    try {
      const data = await fetcher();
      setState({ data, error: null, loading: false });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Unknown error";
      setState((prev) => ({ data: prev.data, error: msg, loading: false }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    load();
    const id = setInterval(load, intervalMs);
    return () => clearInterval(id);
  }, [load, intervalMs]);

  return { ...state, refresh: load };
}
