import { useState, useEffect, useCallback, useRef } from 'react';

export function usePolling<T>(fetcher: () => Promise<T>, _intervalSec: number) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const load = useCallback(async () => {
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => { load(); return () => clearInterval(timer.current); }, [load]);

  const startPolling = useCallback((sec: number) => {
    clearInterval(timer.current);
    timer.current = setInterval(load, sec * 1000);
  }, [load]);

  const stopPolling = useCallback(() => clearInterval(timer.current), []);

  return { data, loading, error, reload: load, startPolling, stopPolling };
}
