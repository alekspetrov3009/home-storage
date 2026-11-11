import { useMemo, useState, type FormEvent } from "react";
import {
  createCategory,
  deleteCategory,
  errorMessage,
  fetchCategories,
  fetchItems,
  renameCategory,
} from "../api";
import { useApi } from "../useApi";
import { Badge, Card, ConfirmDialog, useBump, useToast } from "../components/ui";

/* Страница настроек (/settings, кнопка ⚙ в шапке). Пока здесь один раздел —
   справочник категорий (добавление, переименование, удаление); новые разделы
   добавляются ниже по той же схеме: заголовок-оверлайн + Card.
   Переименование обновляет категорию у всех вещей; удаление делает вещи
   «без категории» (обратного хода нет — поэтому confirm). */
export default function Settings() {
  const categories = useApi(fetchCategories);
  const items = useApi(fetchItems);
  const bump = useBump();
  const toast = useToast();

  const [newName, setNewName] = useState("");
  const [busyAdd, setBusyAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [busyEdit, setBusyEdit] = useState(false);
  const [deleting, setDeleting] = useState<{ name: string; count: number } | null>(null);
  const [busyDelete, setBusyDelete] = useState(false);

  // Сколько вещей в каждой категории (для подтверждения удаления).
  const counts = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of items.data ?? []) {
      const key = item.category.trim().toLowerCase();
      if (!key) continue;
      map.set(key, (map.get(key) ?? 0) + 1);
    }
    return map;
  }, [items.data]);

  const submitAdd = async (event: FormEvent) => {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setBusyAdd(true);
    try {
      await createCategory(name);
      setNewName("");
      bump();
      toast(`Категория «${name}» добавлена`);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusyAdd(false);
    }
  };

  const startEdit = (name: string) => {
    setEditing(name);
    setEditValue(name);
  };

  const cancelEdit = () => {
    setEditing(null);
    setEditValue("");
  };

  const submitEdit = async () => {
    if (!editing || busyEdit) return;
    const next = editValue.trim();
    if (!next || next === editing) {
      cancelEdit();
      return;
    }
    setBusyEdit(true);
    try {
      const result = await renameCategory(editing, next);
      setEditing(null);
      setEditValue("");
      bump();
      toast(
        result.items_updated
          ? `Категория переименована, вещей обновлено: ${result.items_updated}`
          : `Категория «${result.name}» переименована`,
      );
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusyEdit(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleting || busyDelete) return;
    setBusyDelete(true);
    try {
      const result = await deleteCategory(deleting.name);
      bump();
      toast(
        result.items_updated
          ? `Категория «${result.name}» удалена, вещей стало «без категории»: ${result.items_updated}`
          : `Категория «${result.name}» удалена`,
      );
      setDeleting(null);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusyDelete(false);
    }
  };

  const list = categories.data ?? [];

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Настройки</h1>
          <p className="page-sub">Справочники и поведение склада</p>
        </div>
      </div>

      <p className="overline">Категории</p>
      <Card className="section">
        <form className="settings-add" onSubmit={submitAdd}>
          <input
            className="input"
            placeholder="Новая категория…"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            aria-label="Название новой категории"
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={busyAdd || !newName.trim()}
          >
            ＋ Добавить
          </button>
        </form>

        {categories.error && <p className="inline-error">{categories.error}</p>}
        {categories.loading && <p className="dim">Загрузка…</p>}
        {!categories.loading && !categories.error && list.length === 0 && (
          <p className="dim">Категорий пока нет — добавьте первую выше.</p>
        )}

        <ul className="settings-list">
          {list.map((name) => {
            const count = counts.get(name.toLowerCase()) ?? 0;
            return (
              <li key={name} className="category-row">
                {editing === name ? (
                  <>
                    <input
                      className="input"
                      value={editValue}
                      autoFocus
                      onChange={(event) => setEditValue(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") cancelEdit();
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void submitEdit();
                        }
                      }}
                      aria-label="Новое название категории"
                    />
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => void submitEdit()}
                      disabled={busyEdit || !editValue.trim()}
                      aria-label="Сохранить"
                    >
                      ✓
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={cancelEdit}
                      aria-label="Отменить переименование"
                    >
                      ✕
                    </button>
                  </>
                ) : (
                  <>
                    <span className="category-name" title={name}>
                      {name}
                    </span>
                    <Badge tone="muted">
                      <span className="num">{count}</span>
                    </Badge>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => startEdit(name)}
                      aria-label={`Переименовать «${name}»`}
                      title="Переименовать"
                    >
                      ✏️
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm category-delete"
                      onClick={() => setDeleting({ name, count })}
                      aria-label={`Удалить «${name}»`}
                      title="Удалить"
                    >
                      🗑
                    </button>
                  </>
                )}
              </li>
            );
          })}
        </ul>

        <p className="dim settings-note">
          Переименование обновит категорию у всех вещей. Удаление не трогает
          вещи — они станут «без категории».
        </p>
      </Card>

      {deleting && (
        <ConfirmDialog
          title="Удалить категорию?"
          message={`Категория «${deleting.name}» будет удалена из справочника.`}
          hint={
            deleting.count
              ? `Вещей с этой категорией: ${deleting.count}. Они станут «без категории»; вернуть категорию можно только вручную.`
              : "Категория сейчас не используется ни у одной вещи."
          }
          confirmLabel="Удалить"
          danger
          busy={busyDelete}
          onConfirm={() => void confirmDelete()}
          onCancel={() => setDeleting(null)}
        />
      )}
    </>
  );
}
