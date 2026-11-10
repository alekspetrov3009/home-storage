import { useEffect, useMemo, useRef, useState } from "react";
import {
  deleteItems,
  fetchBoxes,
  fetchCategories,
  fetchItems,
  saveItemsTable,
  type Box,
  type Item,
  type ItemSaveRow,
} from "../api";
import { useApi } from "../useApi";
import {
  Badge,
  Card,
  ConfirmDialog,
  ErrorState,
  useBump,
  useToast,
  useUndo,
} from "../components/ui";
import { formatDate } from "../api";

interface EditRow {
  id: string;
  name: string;
  box_id: string;
  quantity: string;
  category: string;
  notes: string;
}

function toEditRow(item: Item): EditRow {
  return {
    id: item.id,
    name: item.name,
    box_id: item.box_id,
    quantity: String(item.quantity),
    category: item.category,
    notes: item.notes,
  };
}

function sameRow(a: EditRow, b: EditRow): boolean {
  return (
    a.id === b.id &&
    a.name === b.name &&
    a.box_id === b.box_id &&
    a.quantity.trim() === b.quantity.trim() &&
    a.category === b.category &&
    a.notes === b.notes
  );
}

/* Подписи ящиков для селекта: у дублей имён — суффикс « · #xxxx»
   (как в helpers.box_label_map backend), только для отображения. */
function boxSelectLabel(boxes: Box[]): Map<string, string> {
  const counts = new Map<string, number>();
  for (const box of boxes) counts.set(box.name, (counts.get(box.name) ?? 0) + 1);
  return new Map(
    boxes.map((box) => [
      box.id,
      (counts.get(box.name) ?? 0) > 1 ? `${box.name} · #${box.id.slice(-4)}` : box.name,
    ]),
  );
}

export default function ItemsTable() {
  const items = useApi(fetchItems);
  const boxes = useApi(fetchBoxes);
  const categories = useApi(fetchCategories);
  const bump = useBump();
  const toast = useToast();
  const undo = useUndo();

  const [rows, setRows] = useState<EditRow[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Данные с сервера — база локального состояния редактора.
  useEffect(() => {
    if (items.data) setRows(items.data.map(toEditRow));
  }, [items.data]);

  // После мутаций (bump) refetch обновит items.data → строки пересоберутся.
  useEffect(() => {
    setSelected(new Set());
    setError(null);
  }, [items.data]);

  const labels = useMemo(
    () => boxSelectLabel(boxes.data ?? []),
    [boxes.data],
  );

  const originals = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of items.data ?? []) map.set(item.id, item);
    return map;
  }, [items.data]);

  const isNew = (row: EditRow) => row.id === "";
  const isChanged = (row: EditRow) => {
    const original = originals.get(row.id);
    return !isNew(row) && original !== undefined && !sameRow(row, toEditRow(original));
  };
  const dirtyCount = useMemo(
    () => (rows ?? []).filter((row) => isNew(row) || isChanged(row)).length,
    [rows, originals],
  );

  const selectableIds = useMemo(
    () => (rows ?? []).filter((row) => !isNew(row)).map((row) => row.id),
    [rows],
  );
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selected.has(id));
  const someSelected = selected.size > 0;

  const allRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (allRef.current) {
      allRef.current.indeterminate = someSelected && !allSelected;
    }
  }, [someSelected, allSelected]);

  const patchRow = (index: number, patch: Partial<EditRow>) => {
    setRows((prev) =>
      prev ? prev.map((row, i) => (i === index ? { ...row, ...patch } : row)) : prev,
    );
  };

  const addRow = () => {
    setRows((prev) => [
      ...(prev ?? []),
      { id: "", name: "", box_id: "", quantity: "1", category: "", notes: "" },
    ]);
  };

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(selectableIds));
  };

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const save = async () => {
    if (!rows) return;
    const emptyName = rows.find((row) => !row.name.trim());
    if (emptyName) {
      setError("Укажите название вещи — в таблице есть строка без названия.");
      return;
    }
    setBusy(true);
    setError(null);
    const payload: ItemSaveRow[] = rows.map((row) => ({
      id: row.id,
      name: row.name.trim(),
      box_id: row.box_id,
      quantity: row.quantity.trim() === "" ? "0" : row.quantity.trim(),
      category: row.category.trim(),
      notes: row.notes,
    }));
    try {
      const { saved } = await saveItemsTable(payload);
      bump();
      toast(`Сохранено строк: ${saved}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setConfirmReset(false);
    setError(null);
    items.refetch();
  };

  const bulkDelete = async () => {
    const ids = [...selected];
    setBusy(true);
    try {
      const entries = await deleteItems(ids);
      bump();
      toast(`Удалено вещей: ${entries.length} — можно отменить`);
      undo.show(`вещи (${entries.length} шт.)`, entries);
      setSelected(new Set());
      setConfirmDelete(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setConfirmDelete(false);
    } finally {
      setBusy(false);
    }
  };

  if (items.error) {
    return <ErrorState message={items.error} />;
  }

  if (items.loading || !rows) {
    return (
      <Card aria-hidden="true">
        <p className="muted">Загружаю таблицу…</p>
      </Card>
    );
  }

  return (
    <>
      <div className="toolbar">
        <button type="button" className="btn btn-outline" onClick={addRow}>
          ＋ Добавить строку
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => (dirtyCount > 0 ? setConfirmReset(true) : reset())}
        >
          Отмена
        </button>
        {dirtyCount > 0 && (
          <Badge tone="warning">Не сохранено изменений: {dirtyCount}</Badge>
        )}
      </div>

      {error && <p className="inline-error mb-16">{error}</p>}

      <div className="table-wrap">
        <table className="items-table">
          <thead>
            <tr>
              <th className="cell-check">
                <input
                  ref={allRef}
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  aria-label="Выбрать все строки"
                />
              </th>
              <th>Название</th>
              <th>Ящик</th>
              <th>Кол-во</th>
              <th>Категория</th>
              <th>Заметки</th>
              <th className="cell-updated">Обновлён</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={row.id || `new-${index}`}
                className={isNew(row) ? "row-new" : isChanged(row) ? "row-changed" : ""}
              >
                <td className="cell-check">
                  <input
                    type="checkbox"
                    disabled={isNew(row)}
                    checked={selected.has(row.id)}
                    onChange={() => toggleOne(row.id)}
                    aria-label={`Выбрать «${row.name || "новая строка"}»`}
                  />
                </td>
                <td className="cell-name">
                  <input
                    className="input"
                    value={row.name}
                    onChange={(event) => patchRow(index, { name: event.target.value })}
                    aria-label="Название"
                  />
                </td>
                <td>
                  <select
                    className="select"
                    value={row.box_id}
                    onChange={(event) => patchRow(index, { box_id: event.target.value })}
                    aria-label="Ящик"
                  >
                    <option value="">— без ящика —</option>
                    {(boxes.data ?? []).map((box) => (
                      <option key={box.id} value={box.id}>
                        {labels.get(box.id)}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="cell-qty">
                  <input
                    className="input num"
                    inputMode="numeric"
                    value={row.quantity}
                    onChange={(event) => patchRow(index, { quantity: event.target.value })}
                    aria-label="Количество"
                  />
                </td>
                <td>
                  <input
                    className="input"
                    value={row.category}
                    list="items-table-categories"
                    onChange={(event) => patchRow(index, { category: event.target.value })}
                    aria-label="Категория"
                  />
                </td>
                <td>
                  <input
                    className="input"
                    value={row.notes}
                    onChange={(event) => patchRow(index, { notes: event.target.value })}
                    aria-label="Заметки"
                  />
                </td>
                <td className="cell-updated num">
                  {isNew(row) ? "новая" : formatDate(originals.get(row.id)?.updated_at ?? "")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <datalist id="items-table-categories">
          {(categories.data ?? []).map((category) => (
            <option key={category} value={category} />
          ))}
        </datalist>
      </div>

      <div className="bulk-bar">
        {someSelected ? (
          <>
            <span className="num">Выбрано: {selected.size}</span>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => setConfirmDelete(true)}
            >
              🗑 Удалить выбранные
            </button>
          </>
        ) : (
          <span className="dim">
            Отметьте строки чекбоксами для массового удаления; подсветка — изменённые строки.
          </span>
        )}
        <span className="spacer" />
        <button
          type="button"
          className="btn btn-primary"
          onClick={save}
          disabled={busy || (dirtyCount === 0 && !rows.some(isNew))}
        >
          💾 Сохранить таблицу
        </button>
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title="Удалить выбранные вещи?"
          message={<>В корзину уедет {selected.size} шт. — их можно восстановить или отменить сразу после удаления.</>}
          confirmLabel="Удалить"
          danger
          busy={busy}
          onConfirm={bulkDelete}
          onCancel={() => setConfirmDelete(false)}
        />
      )}

      {confirmReset && (
        <ConfirmDialog
          title="Отменить правки?"
          message="Несохранённые изменения строк будут потеряны."
          confirmLabel="Отменить правки"
          danger
          onConfirm={reset}
          onCancel={() => setConfirmReset(false)}
        />
      )}
    </>
  );
}
