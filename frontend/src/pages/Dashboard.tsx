import { Link } from "react-router-dom";
import { fetchItems, fetchStats, type Item } from "../api";
import { useApi } from "../useApi";
import { Card, EmptyState, ErrorState, Skeleton, SkeletonGrid } from "../components/ui";
import ItemCard from "../components/ItemCard";

export default function Dashboard() {
  const stats = useApi(fetchStats);
  const items = useApi(fetchItems);

  const recent: Item[] = (items.data ?? [])
    .slice()
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    .slice(0, 5);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Обзор</h1>
          <p className="page-sub">Сводка по хранилищу</p>
        </div>
        <Link to="/add" className="btn btn-primary">
          ＋ Добавить вещь
        </Link>
      </div>

      {stats.error && <ErrorState message={stats.error} hint="Проверьте, что backend запущен на порту 8000." />}

      {stats.loading && (
        <div className="stats-grid" aria-hidden="true">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} />
          ))}
        </div>
      )}

      {stats.data && (
        <section className="stats-grid section" aria-label="Статистика склада">
          <Card className="stat-tile stat-hero">
            <div>
              <div className="stat-num">{stats.data.units}</div>
              <div className="stat-label">единиц на складе</div>
            </div>
            <Link to="/add" className="btn btn-primary btn-sm">
              ＋ Добавить вещь
            </Link>
          </Card>
          <Card className="stat-tile">
            <div className="stat-num">{stats.data.boxes}</div>
            <div className="stat-label">ящиков</div>
          </Card>
          <Card className="stat-tile">
            <div className="stat-num">{stats.data.items}</div>
            <div className="stat-label">вещей</div>
          </Card>
          <Card className="stat-tile">
            <div className="stat-num">{stats.data.locations}</div>
            <div className="stat-label">мест хранения</div>
          </Card>
        </section>
      )}

      <h2 className="overline">Недавно обновлённое</h2>

      {items.error && <ErrorState message={items.error} />}
      {items.loading && <SkeletonGrid count={5} />}

      {items.data &&
        (recent.length === 0 ? (
          <EmptyState
            icon="🧾"
            title="Пока нет ни одной вещи"
            hint="Добавьте первую вещь — она появится здесь."
            action={
              <Link to="/add" className="btn btn-primary">
                ＋ Добавить вещь
              </Link>
            }
          />
        ) : (
          <div className="grid-cards">
            {recent.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        ))}
    </>
  );
}
