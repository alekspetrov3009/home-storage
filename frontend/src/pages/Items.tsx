import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchBoxes, fetchItems, fetchLocations, type Box, type Item } from "../api";
import { useApi } from "../useApi";
import { useAuth } from "../auth";
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
const NO_LOCATION = "__no_location__";

interface ItemGroup {
  key: string;
  name: string;
  items: Item[];
}

function savedView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === "table" ? "table" : "cards";
  } catch {
    return "cards";
  }
}

export default function Items() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  // Таблица доступна всем: админам — bulk-редактор, роли «просмотр» — только чтение.
  const [view, setView] = useState<View>(savedView);
  const [locationFilter, setLocationFilter] = useState("");
  const [boxFilter, setBoxFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const boxes = useApi(fetchBoxes);
  const locations = useApi(fetchLocations);
  const items = useApi(fetchItems);

  const noItems = !!items.data && items.data.length === 0;
  const hasItems = !!items.data && items.data.length > 0;

  const emptyWarehouse =
    noItems &&
    !!boxes.data &&
    boxes.data.length === 0 &&
    !!locations.data &&
    locations.data.length === 0;

  const firstRun = isAdmin && emptyWarehouse;

  // Раскладка (фильтры, пустые состояния) зависит от всех трёх списков —
  // до их загрузки показываем только скелет, чтобы ничего не мигало.
  const ready =
    (!!items.data || !!items.error) &&
    (!!boxes.data || !!boxes.error) &&
    (!!locations.data || !!locations.error);

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_KEY, view);
    } catch {
      /* выбор вида не критичен */
    }
  }, [view]);

  // Вещь → место: через её ящик; ящики с удалённым местом считаются «без места».
  const boxLocation = useMemo(() => {
    const map = new Map<string, string>();
    for (const box of boxes.data ?? []) {
      if (box.location_id && box.location_name) map.set(box.id, box.location_id);
    }
    return map;
  }, [boxes.data]);

  const locationNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const location of locations.data ?? []) map.set(location.id, location.name);
    return map;
  }, [locations.data]);

  // Шаг 1: вещи выбранного места.
  const atLocation = useMemo(() => {
    const data = items.data;
    if (!data) return [];
    if (!locationFilter) return data;
    return data.filter((item) => {
      const locId = boxLocation.get(item.box_id) ?? "";
      return locationFilter === NO_LOCATION ? locId === "" : locId === locationFilter;
    });
  }, [items.data, locationFilter, boxLocation]);

  // Ящики выбранного места (для чипов и группировки).
  const availableBoxes = useMemo<Box[]>(() => {
    const data = boxes.data ?? [];
    if (!locationFilter) return data;
    if (locationFilter === NO_LOCATION) {
      return data.filter((box) => !(box.location_id && box.location_name));
    }
    return data.filter((box) => box.location_id === locationFilter);
  }, [boxes.data, locationFilter]);

  // Шаг 2: вещи выбранного места и ящика — из них складываются категории.
  const inBox = useMemo(
    () => atLocation.filter((item) => !boxFilter || item.box_id === boxFilter),
    [atLocation, boxFilter],
  );

  const availableCategories = useMemo(() => {
    const set = new Set<string>();
    for (const item of inBox) {
      if (item.category) set.add(item.category);
    }
    return [...set].sort((a, b) => a.localeCompare(b, "ru"));
  }, [inBox]);

  // Шаг 3: плюс выбранная категория — итоговый список.
  const located = useMemo(
    () =>
      inBox.filter((item) => !categoryFilter || item.category === categoryFilter),
    [inBox, categoryFilter],
  );

  // Смена места может сделать выбранные ящик/категорию недоступными — сбрасываем.
  useEffect(() => {
    if (boxFilter && !availableBoxes.some((box) => box.id === boxFilter)) {
      setBoxFilter("");
    }
  }, [boxFilter, availableBoxes]);

  useEffect(() => {
    if (categoryFilter && !availableCategories.includes(categoryFilter)) {
      setCategoryFilter("");
    }
  }, [categoryFilter, availableCategories]);

  const groups = useMemo<ItemGroup[]>(() => {
    const byKey = new Map<string, ItemGroup>();
    for (const item of located) {
      const locId = boxLocation.get(item.box_id) ?? "";
      const key = locId || NO_LOCATION;
      const group = byKey.get(key) ?? {
        key,
        name: locationNames.get(locId) ?? "Без места хранения",
        items: [],
      };
      group.items.push(item);
      byKey.set(key, group);
    }
    return [...byKey.values()].sort((a, b) => {
      if (a.key === NO_LOCATION) return 1;
      if (b.key === NO_LOCATION) return -1;
      return a.name.localeCompare(b.name, "ru");
    });
  }, [located, boxLocation, locationNames]);

  const filtered = Boolean(boxFilter || categoryFilter || locationFilter);

  const resetFilters = () => {
    setLocationFilter("");
    setBoxFilter("");
    setCategoryFilter("");
  };

  return (
    <>
      {firstRun ? (
        <div className="first-run">
          <EmptyState
            icon="🧾"
            title="Пока нет ни одной вещи"
            hint="Добавьте первую вещь на склад."
            action={
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={() => navigate("/add")}
              >
                ＋ Создать
              </button>
            }
          />
        </div>
      ) : !ready ? (
        <SkeletonGrid />
      ) : (
        <>
          <div className="page-header">
            <div>
              <h1>Вещи</h1>
              <p className="page-sub">
                {items.data ? `Найдено: ${located.length}` : "Что и где лежит"}
              </p>
            </div>
            <div className="page-header-actions">
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
              {isAdmin && (
                <Link to="/add" className="btn btn-primary">
                  ＋ Добавить вещь
                </Link>
              )}
            </div>
          </div>

          {view === "cards" ? (
            <>
              {hasItems && (
                <>
                  <div className="section" style={{ maxWidth: 320 }}>
                    <select
                      className="select"
                      value={locationFilter}
                      onChange={(event) => setLocationFilter(event.target.value)}
                      aria-label="Место хранения"
                    >
                      <option value="">Все места</option>
                      {(locations.data ?? []).map((location) => (
                        <option key={location.id} value={location.id}>
                          {location.name}
                        </option>
                      ))}
                      <option value={NO_LOCATION}>— без места —</option>
                    </select>
                  </div>
                  <div className="chips-row section">
                    <Chip active={!boxFilter} onClick={() => setBoxFilter("")}>
                      Все ящики
                    </Chip>
                    {availableBoxes.map((box) => (
                      <Chip
                        key={box.id}
                        active={boxFilter === box.id}
                        onClick={() => setBoxFilter(boxFilter === box.id ? "" : box.id)}
                      >
                        <span
                          className="box-color-dot sm"
                          style={{ background: box.color }}
                          aria-hidden="true"
                        />
                        {box.name}
                      </Chip>
                    ))}
                  </div>
                  <div className="chips-row section">
                    <Chip active={!categoryFilter} onClick={() => setCategoryFilter("")}>
                      Все категории
                    </Chip>
                    {availableCategories.map((category) => (
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
                </>
              )}

              {items.error && <ErrorState message={items.error} />}
              {items.loading && <SkeletonGrid />}
              {items.data &&
                (items.data.length === 0 ? (
                  <EmptyState
                    icon="🧾"
                    title="Пока нет ни одной вещи"
                    hint="Добавьте первую вещь на склад."
                    action={
                      isAdmin ? (
                        <Link to="/add" className="btn btn-primary">
                          ＋ Добавить вещь
                        </Link>
                      ) : undefined
                    }
                  />
                ) : located.length === 0 ? (
                  <Card>
                    <EmptyState
                      icon="🔍"
                      title="Под фильтр ничего не подошло"
                      hint="Сбросьте фильтры или добавьте вещь."
                      action={
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={resetFilters}
                        >
                          Сбросить фильтры
                        </button>
                      }
                    />
                  </Card>
                ) : (
                  groups.map((group) => (
                    <section key={group.key} className="section">
                      <h2 className="overline">
                        {group.name} · {group.items.length}
                      </h2>
                      <div className="grid-cards">
                        {group.items.map((item) => (
                          <ItemCard key={item.id} item={item} />
                        ))}
                      </div>
                    </section>
                  ))
                ))}
            </>
          ) : (
            <>
              {isAdmin && filtered && (
                <p className="dim mb-16">
                  Массовое сохранение перезаписывает весь лист целиком: фильтры таблицы
                  скрывают строки только на экране, при сохранении записываются все строки.
                </p>
              )}
              <ItemsTable readOnly={!isAdmin} />
            </>
          )}
        </>
      )}
    </>
  );
}
