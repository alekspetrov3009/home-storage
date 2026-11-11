import { useState } from "react";
import {
  clearTrash,
  fetchBoxes,
  fetchLocations,
  fetchTrash,
  formatDate,
  restoreFromTrash,
  type TrashEntry,
} from "../api";
import { useApi } from "../useApi";
import { useAuth } from "../auth";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  SkeletonGrid,
  useBump,
  useToast,
} from "../components/ui";

const KIND_LABEL: Record<string, string> = {
  item: "вещь",
  box: "ящик",
  location: "место",
};

const KIND_ICON: Record<string, string> = {
  item: "🧾",
  box: "📦",
  location: "🗺",
};

function originLabel(entry: TrashEntry, boxNames: Map<string, string>, locationNames: Map<string, string>): string {
  if (entry.kind === "item") {
    const name = boxNames.get(entry.parent_id);
    return name ? `из ящика «${name}»` : "происхождение неизвестно";
  }
  if (entry.kind === "box") {
    const name = locationNames.get(entry.parent_id);
    return name ? `из места «${name}»` : "без места хранения";
  }
  return "место хранения";
}

export default function Trash() {
  const trash = useApi(fetchTrash);
  const boxes = useApi(fetchBoxes);
  const locations = useApi(fetchLocations);
  const { isAdmin } = useAuth();
  const bump = useBump();
  const toast = useToast();

  const [armed, setArmed] = useState(false); // двухшаговое подтверждение очистки
  const [busy, setBusy] = useState(false);

  const restore = async (entry: TrashEntry) => {
    try {
      const { name } = await restoreFromTrash(entry.kind, entry.id);
      bump();
      toast(`Восстановлено: ${name}`);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  };

  const clear = async () => {
    setBusy(true);
    try {
      const { deleted } = await clearTrash();
      bump();
      toast(`Корзина очищена: удалено записей ${deleted}`);
      setArmed(false);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setArmed(false);
    } finally {
      setBusy(false);
    }
  };

  const boxNames = new Map((boxes.data ?? []).map((box) => [box.id, box.name]));
  const locationNames = new Map((locations.data ?? []).map((loc) => [loc.id, loc.name]));

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Корзина</h1>
          <p className="page-sub">
            Удалённое можно вернуть; записи старше 30 дней вычищаются автоматически
            {trash.data && trash.data.purged > 0
              ? ` · вычищено просроченных: ${trash.data.purged}`
              : ""}
          </p>
        </div>
        {isAdmin && trash.data && trash.data.entries.length > 0 && (
          <div className="row">
            {!armed ? (
              <button type="button" className="btn btn-danger" onClick={() => setArmed(true)}>
                🗑 Очистить корзину
              </button>
            ) : (
              <>
                <span className="dim">Точно очистить всю корзину?</span>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={clear}
                  disabled={busy}
                >
                  Да, очистить
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setArmed(false)}
                >
                  Отмена
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {trash.error && <ErrorState message={trash.error} />}
      {trash.loading && <SkeletonGrid />}
      {trash.data &&
        (trash.data.entries.length === 0 ? (
          <EmptyState
            icon="🗑"
            title="Корзина пуста"
            hint="Удалённые вещи, ящики и места попадают сюда и живут 30 дней."
          />
        ) : (
          <div className="grid-cards">
            {trash.data.entries.map((entry) => (
              <Card key={entry.id} className="box-card">
                <div className="box-card-title">
                  <span>
                    {KIND_ICON[entry.kind] ?? "❔"} {entry.name}
                  </span>
                  <Badge tone={entry.kind === "item" ? "muted" : "warning"}>
                    {KIND_LABEL[entry.kind] ?? entry.kind}
                  </Badge>
                </div>
                <p className="dim">{originLabel(entry, boxNames, locationNames)}</p>
                <p className="dim num">Удалено: {formatDate(entry.deleted_at)}</p>
                {isAdmin && (
                  <div className="row mt-8">
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => restore(entry)}
                    >
                      ↩️ Восстановить
                    </button>
                  </div>
                )}
              </Card>
            ))}
          </div>
        ))}
    </>
  );
}
