import { useEffect, useState } from "react";
import { fetchStats, type Stats } from "./api";

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="page">
      <header className="hero">
        <h1>Домашний склад</h1>
        <p className="hero-caption">Сводка по хранилищу</p>
      </header>

      {loading && <p className="state">Загружаю данные…</p>}

      {error && (
        <div className="state error-state" role="alert">
          <p>Не удалось получить данные от API.</p>
          <p className="state-hint">{error}</p>
          <p className="state-hint">
            Проверьте, что backend запущен на порту 8000.
          </p>
        </div>
      )}

      {stats && (
        <section className="stats">
          <article className="stat-card">
            <div className="stat-icon">📦</div>
            <div className="stat-num">{stats.boxes}</div>
            <div className="stat-label">ящиков</div>
          </article>
          <article className="stat-card">
            <div className="stat-icon">🗃</div>
            <div className="stat-num">{stats.items}</div>
            <div className="stat-label">вещей</div>
          </article>
          <article className="stat-card">
            <div className="stat-icon">🔢</div>
            <div className="stat-num">{stats.units}</div>
            <div className="stat-label">единиц</div>
          </article>
          <article className="stat-card">
            <div className="stat-icon">🗺</div>
            <div className="stat-num">{stats.locations}</div>
            <div className="stat-label">мест хранения</div>
          </article>
        </section>
      )}
    </main>
  );
}
