import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchBoxes, fetchCategories, fetchItems } from "../api";
import { useApi } from "../useApi";
import {
  Card,
  Chip,
  EmptyState,
  ErrorState,
  SkeletonGrid,
} from "../components/ui";
import ItemCard from "../components/ItemCard";
import ItemsTable from "./ItemsTable";

type View = "cards" | "table";

const VIEW_KEY = "hs-items-view";

function savedView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === "table" ? "table" : "cards";
  } catch {
    return "cards";
  }
}

export default function Items() {
  const [view, setView] = useState<View>(savedView);
  const [boxFilter, setBoxFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const boxes = useApi(fetchBoxes);
  const categories = useApi(fetchCategories);
  const items = useApi(
    () => fetchItems({ box_id: boxFilter, category: categoryFilter }),
    [boxFilter, categoryFilter],
  );

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_KEY, view);
    } catch {
      /* выбор вида не критичен */
    }
  }, [view]);

  const filtered = Boolean(boxFilter || categoryFilter);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Вещи</h1>
          <p className="page-sub">
            {items.data ? `Найдено: ${items.data.length}` : "Что и где лежит"}
          </p>
        </div>
        <span className="segmented" role="tablist" aria-label="Вид списка">
          <button
            type="button"
            className={`segmented-btn${view === "cards" ? " active" : ""}`}
            onClick={() => setView("cards")}
          >
            Карточки
          </button>
          <button
            type="button"
            className={`segmented-btn${view === "table" ? " active" : ""}`}
            onClick={() => setView("table")}
          >
            Таблица
          </button>
        </span>
      </div>

      {view === "cards" ? (
        <>
          <div className="chips-row section">
            <Chip active={!boxFilter} onClick={() => setBoxFilter("")}>
              Все ящики
            </Chip>
            {(boxes.data ?? []).map((box) => (
              <Chip
                key={box.id}
                active={boxFilter === box.id}
                onClick={() => setBoxFilter(boxFilter === box.id ? "" : box.id)}
              >
                {box.name}
              </Chip>
            ))}
          </div>
          <div className="chips-row section">
            <Chip active={!categoryFilter} onClick={() => setCategoryFilter("")}>
              Все категории
            </Chip>
            {(categories.data ?? []).map((category) => (
              <Chip
                key={category}
                active={categoryFilter === category}
                onClick={() =>
                  setCategoryFilter(categoryFilter === category ? "" : category)
                }
              >
                {category}
              </Chip>
            ))}
          </div>

          {items.error && <ErrorState message={items.error} />}
          {items.loading && <SkeletonGrid />}
          {items.data &&
            (items.data.length === 0 ? (
              filtered ? (
                <Card>
                  <EmptyState
                    icon="🔍"
                    title="Под фильтр ничего не подошло"
                    hint="Сбросьте фильтры или добавьте вещь."
                    action={
                      <button
                        type="button"
                        className="btn btn-outline"
                        onClick={() => {
                          setBoxFilter("");
                          setCategoryFilter("");
                        }}
                      >
                        Сбросить фильтры
                      </button>
                    }
                  />
                </Card>
              ) : (
                <EmptyState
                  icon="🧾"
                  title="Пока нет ни одной вещи"
                  hint="Добавьте первую вещь на склад."
                  action={
                    <Link to="/add" className="btn btn-primary">
                      ＋ Добавить вещь
                    </Link>
                  }
                />
              )
            ) : (
              <div className="grid-cards">
                {items.data.map((item) => (
                  <ItemCard key={item.id} item={item} />
                ))}
              </div>
            ))}
        </>
      ) : (
        <>
          {filtered && (
            <p className="dim mb-16">
              Таблица всегда показывает все вещи: массовое сохранение перезаписывает
              весь лист. Фильтры действуют только на карточки.
            </p>
          )}
          <ItemsTable />
        </>
      )}
    </>
  );
}
