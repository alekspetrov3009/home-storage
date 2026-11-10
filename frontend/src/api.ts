/* REST-клиент: типы повторяют схемы backend/app/api/schemas.py (snake_case),
   ошибки API — {"detail": "текст"} и показываются пользователю как есть. */

export interface Stats {
  boxes: number;
  items: number;
  units: number;
  locations: number;
}

export interface Location {
  id: string;
  name: string;
  description: string;
  created_at: string;
  box_count: number;
}

export interface Box {
  id: string;
  name: string;
  location_id: string;
  location_name: string | null;
  description: string;
  created_at: string;
  item_count: number;
  unit_count: number;
  color: string;
}

export interface BoxDetail extends Box {
  items: Item[];
}

export interface Item {
  id: string;
  name: string;
  box_id: string;
  box_label: string | null;
  quantity: number;
  category: string;
  notes: string;
  updated_at: string;
}

export type TrashKind = "item" | "box" | "location";

export interface TrashEntry {
  id: string;
  kind: TrashKind;
  name: string;
  parent_id: string;
  deleted_at: string;
  data: Record<string, unknown>;
}

export interface TrashResponse {
  entries: TrashEntry[];
  purged: number;
}

export interface ItemSaveRow {
  id: string;
  name: string;
  box_id: string;
  quantity: string | number;
  category: string;
  notes: string;
}

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      0,
      `Нет связи с API (${API_URL}). Проверьте, что backend запущен.`,
    );
  }
  if (!response.ok) {
    let detail = `API вернул статус ${response.status}`;
    try {
      const body: unknown = await response.json();
      const detailField = (body as { detail?: unknown } | null)?.detail;
      if (typeof detailField === "string" && detailField) detail = detailField;
    } catch {
      /* тело не JSON — остаётся текст со статусом */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

/* ------------------------------ Чтение ----------------------------------- */

export const fetchStats = () => request<Stats>("/api/stats");

export const fetchLocations = () => request<Location[]>("/api/locations");

export const fetchBoxes = () => request<Box[]>("/api/boxes");

export const fetchBox = (id: string) =>
  request<BoxDetail>(`/api/boxes/${encodeURIComponent(id)}`);

export const fetchItems = (filters?: { box_id?: string; category?: string }) => {
  const params = new URLSearchParams();
  if (filters?.box_id) params.set("box_id", filters.box_id);
  if (filters?.category) params.set("category", filters.category);
  const qs = params.toString();
  return request<Item[]>(`/api/items${qs ? `?${qs}` : ""}`);
};

export const fetchItem = (id: string) => {
  // Отдельной схемы вещи нет — фильтр по точному ID не предусмотрен;
  // детальная страница берёт вещь из общего списка.
  return fetchItems().then((items) => {
    const found = items.find((item) => item.id === id);
    if (!found) {
      throw new ApiError(404, `Вещь с ID ${id} не найдена (возможно, удалена).`);
    }
    return found;
  });
};

export const fetchCategories = () => request<string[]>("/api/categories");

export const fetchTrash = () => request<TrashResponse>("/api/trash");

export const searchItems = (q: string) =>
  // Контракт сервера: стог сена в нижнем регистре, запрос сравнивается как есть —
  // поэтому запрос приводит к нижнему регистру фронтенд.
  request<Item[]>(`/api/search?q=${encodeURIComponent(q.trim().toLowerCase())}`);

/* ----------------------------- Мутации ----------------------------------- */

export interface LocationInput {
  name: string;
  description: string;
}

export const createLocation = (payload: LocationInput) =>
  request<Location>("/api/locations", jsonInit("POST", payload));

export interface LocationPatch {
  name?: string;
  description?: string;
}

export const updateLocation = (id: string, payload: LocationPatch) =>
  request<Location>(`/api/locations/${encodeURIComponent(id)}`, jsonInit("PATCH", payload));

export const deleteLocation = (id: string) =>
  request<TrashEntry>(`/api/locations/${encodeURIComponent(id)}`, { method: "DELETE" });

export interface BoxInput {
  name: string;
  location_id: string;
  description: string;
}

export const createBox = (payload: BoxInput) =>
  request<Box>("/api/boxes", jsonInit("POST", payload));

export interface BoxPatch {
  name?: string;
  location_id?: string;
  description?: string;
}

export const updateBox = (id: string, payload: BoxPatch) =>
  request<BoxDetail>(`/api/boxes/${encodeURIComponent(id)}`, jsonInit("PATCH", payload));

export const deleteBox = (id: string) =>
  request<TrashEntry>(`/api/boxes/${encodeURIComponent(id)}`, { method: "DELETE" });

export interface ItemInput {
  name: string;
  box_id: string;
  quantity: number;
  category: string;
  notes: string;
}

export const createItem = (payload: ItemInput) =>
  request<Item>("/api/items", jsonInit("POST", payload));

export interface ItemPatch {
  name?: string;
  quantity?: number;
  category?: string;
  notes?: string;
  box_id?: string;
}

export const updateItem = (id: string, payload: ItemPatch) =>
  request<Item>(`/api/items/${encodeURIComponent(id)}`, jsonInit("PATCH", payload));

export const moveItem = (id: string, boxId: string) =>
  request<Item>(`/api/items/${encodeURIComponent(id)}/move`, jsonInit("POST", { box_id: boxId }));

export const deleteItem = (id: string) =>
  request<TrashEntry>(`/api/items/${encodeURIComponent(id)}`, { method: "DELETE" });

export const deleteItems = (ids: string[]) =>
  request<TrashEntry[]>(
    `/api/items?ids=${encodeURIComponent(ids.join(","))}`,
    { method: "DELETE" },
  );

export const saveItemsTable = (rows: ItemSaveRow[]) =>
  request<{ saved: number }>("/api/items", jsonInit("PUT", { items: rows }));

export const restoreFromTrash = (kind: TrashKind, id: string) =>
  request<{ name: string }>(
    `/api/trash/${kind}/${encodeURIComponent(id)}/restore`,
    { method: "POST" },
  );

export const clearTrash = () =>
  request<{ deleted: number }>("/api/trash", { method: "DELETE" });

export const createBackup = () =>
  request<{ path: string }>("/api/backup", { method: "POST" });

/* --------------------------- Формат данных ------------------------------- */

/* Даты backend — «YYYY-MM-DD HH:MM:SS» (app.domain.fields.now_str). */

export function formatDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})(?::\d{2})?$/.exec(value);
  if (!match) return value;
  const [, y, m, d, time] = match;
  return `${d}.${m}.${y} ${time}`;
}
