import { useEffect, useMemo, useRef, useState } from "react";
import {
  deleteItems,
  fetchBoxes,
  fetchCategories,
  fetchItems,
  fetchLocations,
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

const NO_LOCATION = "__no_location__";
const NEW_CATEGORY_OPTION = "__new_category__";

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

function contains(haystack: string, needle: string): boolean {
  const query = needle.trim().toLowerCase();
  return query === "" || haystack.toLowerCase().includes(query);
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

function CategoryCell({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (next: string) => void;
}) {
  const [typing, setTyping] = useState(false);

  if (typing) {
    return (
      <input
        className="input"
        value={value}
        autoFocus
        placeholder="Название новой категории"
        aria-label="Новая категория"
        onChange={(event) => onChange(event.target.value)}
        onBlur={() => setTyping(false)}
        onKeyDown={(event) => {
          if (event.key === "Enter") setTyping(false);
        }}
      />
    );
  }

  return (
    <select
      className="select"
      value={value}
      aria-label="Категория"
      onChange={(event) => {
        const next = event.target.value;
        if (next === NEW_CATEGORY_OPTION) {
          setTyping(true);
          return;
        }
        onChange(next);
      }}
    >
      <option value="">— без категории —</option>
      {options.map((category) => (
        <option key={category} value={category}>
          {category}
        </option>
      ))}
      {value && !options.includes(value) && <option value={value}>{value}</option>}
      <option value={NEW_CATEGORY_OPTION}>➕ Новая категория…</option>
    </select>
  );
}

export default function ItemsTable({ readOnly = false }: { readOnly?: boolean }) {
  const items = useApi(fetchItems);
  const boxes = useApi(fetchBoxes);
  const locations = useApi(fetchLocations);
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

  const [locationFilter, setLocationFilter] = useState("");
  const [boxFilter, setBoxFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [nameFilter, setNameFilter] = useState("");
  const [notesFilter, setNotesFilter] = useState("");

  useEffect(() => {
    if (items.data) setRows(items.data.map(toEditRow));
  }, [items.data]);

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

  const boxLocation = useMemo(() => {
    const map = new Map<string, string>();
    for (const box of boxes.data ?? []) {
      if (box.location_id && box.location_name) map.set(box.id, box.location_id);
    }
    return map;
  }, [boxes.data]);

  const matchesLocation = (row: EditRow): boolean => {
    if (!locationFilter) return true;
    const locId = boxLocation.get(row.box_id) ?? "";
    return locationFilter === NO_LOCATION ? locId === "" : locId === locationFilter;
  };

  const availableBoxes = useMemo(() => {
    const data = boxes.data ?? [];
    if (!locationFilter) return data;
    if (locationFilter === NO_LOCATION) {
      return data.filter((box) => !(box.location_id && box.location_name));
    }
    return data.filter((box) => box.location_id === locationFilter);
  }, [boxes.data, locationFilter]);

  // Строки выбранного места и ящика — источник вариантов фильтра категорий.
  const scopedRows = useMemo(
    () =>
      (rows ?? []).filter(
        (row) => matchesLocation(row) && (!boxFilter || row.box_id === boxFilter),
      ),
    [rows, boxFilter, locationFilter, boxLocation],
  );

  const availableCategories = useMemo(() => {
    const set = new Set<string>();
    for (const row of scopedRows) {
      if (row.category) set.add(row.category);
    }
    return [...set].sort((a, b) => a.localeCompare(b, "ru"));
  }, [scopedRows]);

  const visible = useMemo(
    () =>
      (rows ?? [])
        .map((row, index) => ({ row, index }))
        .filter(
          ({ row }) =>
            matchesLocation(row) &&
            (!boxFilter || row.box_id === boxFilter) &&
            (!categoryFilter || row.category === categoryFilter) &&
            contains(row.name, nameFilter) &&
            contains(row.notes, notesFilter),
        ),
    [rows, boxFilter, categoryFilter, nameFilter, notesFilter, locationFilter, boxLocation],
  );

  const visibleIds = useMemo(
    () => new Set(visible.map(({ row }) => row.id).filter((id) => id !== "")),
    [visible],
  );

  useEffect(() => {
    setSelected((prev) => {
      const next = new Set([...prev].filter((id) => visibleIds.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [visibleIds]);

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
    () => visible.map(({ row }) => row.id).filter((id) => id !== ""),
    [visible],
  );
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selected.has(id));
  const someSelected = selected.size > 0;
  const tableFiltered = visible.length !== (rows ?? []).length;

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
        <select
          className="select toolbar-select"
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
        {!readOnly && (
          <button type="button" className="btn btn-outline" onClick={addRow}>
            ＋ Добавить строку
          </button>
        )}
        {!readOnly && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => (dirtyCount > 0 ? setConfirmReset(true) : reset())}
          >
            Отмена
          </button>
        )}
        {!readOnly && dirtyCount > 0 && (
          <Badge tone="warning">Не сохранено изменений: {dirtyCount}</Badge>
        )}
        {!readOnly && tableFiltered && (
          <Badge tone="muted">
            Показано: {visible.length} из {rows.length} — при сохранении пишется вся таблица
          </Badge>
        )}
      </div>

      {error && <p className="inline-error mb-16">{error}</p>}

      <div className="table-wrap">
        <table className="items-table">
          <thead>
            <tr>
              {!readOnly && (
                <th className="cell-check">
                  <input
                    ref={allRef}
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    aria-label="Выбрать все видимые строки"
                  />
                </th>
              )}
              <th>Название</th>
              <th>Ящик</th>
              <th>Кол-во</th>
              <th>Категория</th>
              <th>Заметки</th>
              <th className="cell-updated">Обновлён</th>
            </tr>
            <tr className="filter-row">
              {!readOnly && <th className="cell-check" />}
              <th>
                <input
                  className="input"
                  value={nameFilter}
                  onChange={(event) => setNameFilter(event.target.value)}
                  placeholder="Фильтр"
                  aria-label="Фильтр по названию"
                />
              </th>
              <th>
                <select
                  className="select"
                  value={boxFilter}
                  onChange={(event) => setBoxFilter(event.target.value)}
                  aria-label="Фильтр по ящику"
                >
                  <option value="">Все ящики</option>
                  {availableBoxes.map((box) => (
                    <option key={box.id} value={box.id}>
                      {box.name}
                    </option>
                  ))}
                </select>
              </th>
              <th />
              <th>
                <select
                  className="select"
                  value={categoryFilter}
                  onChange={(event) => setCategoryFilter(event.target.value)}
                  aria-label="Фильтр по категории"
                >
                  <option value="">Все категории</option>
                  {availableCategories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </th>
              <th>
                <input
                  className="input"
                  value={notesFilter}
                  onChange={(event) => setNotesFilter(event.target.value)}
                  placeholder="Фильтр"
                  aria-label="Фильтр по заметкам"
                />
              </th>
              <th className="cell-updated" />
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={readOnly ? 6 : 7} className="table-empty">
                  Под фильтры ничего не подошло.
                </td>
              </tr>
            ) : (
              visible.map(({ row, index }) => (
                <tr
                  key={row.id || `new-${index}`}
                  className={isNew(row) ? "row-new" : isChanged(row) ? "row-changed" : ""}
                >
                  {!readOnly && (
                    <td className="cell-check">
                      <input
                        type="checkbox"
                        disabled={isNew(row)}
                        checked={selected.has(row.id)}
                        onChange={() => toggleOne(row.id)}
                        aria-label={`Выбрать «${row.name || "новая строка"}»`}
                      />
                    </td>
                  )}
                  <td className="cell-name">
                    {readOnly ? (
                      row.name
                    ) : (
                      <input
                        className="input"
                        value={row.name}
                        onChange={(event) => patchRow(index, { name: event.target.value })}
                        aria-label="Название"
                      />
                    )}
                  </td>
                  <td>
                    {readOnly ? (
                      labels.get(row.box_id) ?? "— без ящика —"
                    ) : (
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
                    )}
                  </td>
                  <td className="cell-qty">
                    {readOnly ? (
                      <span className="num">{row.quantity}</span>
                    ) : (
                      <input
                        className="input num"
                        inputMode="numeric"
                        value={row.quantity}
                        onChange={(event) => patchRow(index, { quantity: event.target.value })}
                        aria-label="Количество"
                      />
                    )}
                  </td>
                  <td>
                    {readOnly ? (
                      row.category || "— без категории —"
                    ) : (
                      <CategoryCell
                        value={row.category}
                        options={categories.data ?? []}
                        onChange={(category) => patchRow(index, { category })}
                      />
                    )}
                  </td>
                  <td>
                    {readOnly ? (
                      row.notes
                    ) : (
                      <input
                        className="input"
                        value={row.notes}
                        onChange={(event) => patchRow(index, { notes: event.target.value })}
                        aria-label="Заметки"
                      />
                    )}
                  </td>
                  <td className="cell-updated num">
                    {isNew(row) ? "новая" : formatDate(originals.get(row.id)?.updated_at ?? "")}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {!readOnly && (
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
      )}

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
