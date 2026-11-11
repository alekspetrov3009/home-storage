import { useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
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
import { useAuth } from "../auth";
import Users from "./Users";
import PasswordChange from "./PasswordChange";

const TABS = [
  { id: "categories", label: "Категории", adminOnly: true },
  { id: "users", label: "Пользователи", adminOnly: true },
  { id: "password", label: "Пароль", adminOnly: false },
] as const;

type TabId = (typeof TABS)[number]["id"];

/* Страница настроек (/settings; открывается из меню пользователя в шапке).
   Доступна любой роли: вкладка «Пароль» — всем, «Категории» и
   «Пользователи» — только администратору (не видны и закрыты на сервере).
   Активная вкладка — в ?tab=; прямые ссылки на недоступную вкладку
   ведут на первую доступную. Новые вкладки добавляются в TABS, разделы
   внутри вкладки — по схеме: оверлайн + Card. */
export default function Settings() {
  const { isAdmin } = useAuth();
  const [params, setParams] = useSearchParams();

  const visibleTabs = TABS.filter((tab) => isAdmin || !tab.adminOnly);
  const requested = params.get("tab");
  const tab =
    visibleTabs.find((t) => t.id === requested)?.id ?? visibleTabs[0].id;

  const selectTab = (next: TabId) => {
    if (next === tab) return;
    setParams(next === visibleTabs[0].id ? {} : { tab: next }, { replace: true });
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Настройки</h1>
          <p className="page-sub">
            {isAdmin ? "Справочники и поведение склада" : "Учётная запись"}
          </p>
        </div>
        {visibleTabs.length > 1 && (
          <div className="segmented" role="tablist" aria-label="Разделы настроек">
            {visibleTabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={`segmented-btn${tab === t.id ? " active" : ""}`}
                onClick={() => selectTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {tab === "categories" && <CategoriesSection />}
      {tab === "users" && <Users />}
      {tab === "password" && <PasswordChange />}
    </>
  );
}

/* Справочник категорий (добавление, переименование, удаление); новые
   разделы добавляются ниже по той же схеме: заголовок-оверлайн + Card.
   Переименование обновляет категорию у всех вещей; удаление делает вещи
   «без категории» (обратного хода нет — поэтому confirm). */
function CategoriesSection() {
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
          ? `Категория «${deleting.name}» удалена, вещей стало «без категории»: ${result.items_updated}`
          : `Категория «${deleting.name}» удалена`,
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
              <li key={name} className="settings-row">
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
                    <span className="settings-name" title={name}>
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
                      className="btn btn-ghost btn-sm settings-delete"
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
