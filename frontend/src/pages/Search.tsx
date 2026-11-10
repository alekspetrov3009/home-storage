import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { searchItems } from "../api";
import { useApi } from "../useApi";
import { Card, EmptyState, ErrorState, SkeletonGrid } from "../components/ui";
import ItemCard from "../components/ItemCard";

export default function Search() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const navigate = useNavigate();
  const [input, setInput] = useState(q);

  const results = useApi(() => searchItems(q), [q]);

  useEffect(() => {
    setInput(q);
  }, [q]);

  // Пустой запрос на сервере вернул бы ВСЕ вещи — фронт требует непустой q.
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;
    setParams({ q: value });
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Поиск</h1>
          <p className="page-sub">
            По названию, категории, заметкам и подписи ящика
          </p>
        </div>
      </div>

      <form className="topbar-search section" onSubmit={submit} role="search">
        <input
          className="input"
          type="search"
          placeholder="Что ищем?"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          autoFocus
        />
      </form>

      {!q ? (
        <Card>
          <EmptyState
            icon="🔍"
            title="Введите запрос"
            hint="Например, «отвёртка» или название ящика."
          />
        </Card>
      ) : results.loading ? (
        <SkeletonGrid />
      ) : results.error ? (
        <ErrorState message={results.error} />
      ) : (results.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon="🔍"
            title={`По запросу «${q}» ничего не найдено`}
            hint="Попробуйте другое слово или проверьте раскладку."
            action={
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => navigate("/items")}
              >
                Открыть все вещи
              </button>
            }
          />
        </Card>
      ) : (
        <>
          <p className="dim num mb-16">Найдено: {(results.data ?? []).length}</p>
          <div className="grid-cards">
            {(results.data ?? []).map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
