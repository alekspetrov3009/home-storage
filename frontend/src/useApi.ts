import { useContext, useEffect, useState, type DependencyList } from "react";
import { DataVersionContext } from "./components/ui";
import { errorMessage } from "./api";

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/* Хук чтения: loading/error + refetch. Автоматически перечитывает данные,
   когда глобальная версия данных растёт (после мутаций через AppProviders). */
export function useApi<T>(fetcher: () => Promise<T>, deps: DependencyList = []): ApiState<T> {
  const { version } = useContext(DataVersionContext);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher().then(
      (result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      },
      (err: unknown) => {
        if (cancelled) return;
        setError(errorMessage(err));
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, version]);

  return { data, loading, error, refetch: () => setTick((t) => t + 1) };
}
