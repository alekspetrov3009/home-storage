import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { errorMessage, restoreFromTrash, type TrashEntry } from "../api";

/* ========================= Версия данных ================================= */

const DataVersionContext = createContext<{ version: number; bump: () => void }>({
  version: 0,
  bump: () => {},
});

export { DataVersionContext };

export function useDataVersion() {
  return useContext(DataVersionContext);
}

/* ============================= Тосты ===================================== */

type ToastKind = "success" | "error";

interface ToastItem {
  id: number;
  text: string;
  kind: ToastKind;
}

const ToastContext = createContext<(text: string, kind?: ToastKind) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const push = useCallback((text: string, kind: ToastKind = "success") => {
    const id = nextId.current++;
    setItems((prev) => [...prev, { id, text, kind }]);
    window.setTimeout(() => {
      setItems((prev) => prev.filter((item) => item.id !== id));
    }, 4000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-wrap">
        {items.map((item) => (
          <div
            key={item.id}
            className={`toast${item.kind === "error" ? " toast-error" : ""}`}
            role="status"
          >
            {item.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/* ========================= Полоса отмены ================================= */

const UNDO_MS = 30_000;

interface UndoState {
  label: string;
  entries: TrashEntry[];
}

const UndoContext = createContext<{
  show: (label: string, entries: TrashEntry[]) => void;
}>({ show: () => {} });

export function useUndo() {
  return useContext(UndoContext);
}

function UndoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<UndoState | null>(null);
  const { bump } = useDataVersion();
  const toast = useToast();

  useEffect(() => {
    if (!state) return;
    const timer = window.setTimeout(() => setState(null), UNDO_MS);
    return () => window.clearTimeout(timer);
  }, [state]);

  const show = useCallback((label: string, entries: TrashEntry[]) => {
    setState({ label, entries });
  }, []);

  const restoreNow = useCallback(async () => {
    if (!state) return;
    const { entries } = state;
    setState(null);
    let restored = 0;
    const errors: string[] = [];
    for (const entry of entries) {
      try {
        await restoreFromTrash(entry.kind, entry.id);
        restored += 1;
      } catch (err) {
        // «Пропущено: N» без причин бесполезно — показываем первые тексты.
        errors.push(errorMessage(err));
      }
    }
    if (errors.length > 0) {
      const shown = errors.slice(0, 2).join("; ");
      const more = errors.length > 2 ? ` (и ещё ${errors.length - 2})` : "";
      toast(
        `Восстановлено: ${restored}, пропущено: ${errors.length}: ${shown}${more}`,
        "error",
      );
    } else {
      toast(`Восстановлено: ${restored}`);
    }
    bump();
  }, [state, toast, bump]);

  return (
    <UndoContext.Provider value={{ show }}>
      {state && (
        <div className="undo-bar" role="alert">
          <span className="undo-label">Только что удалено: {state.label}</span>
          <button type="button" className="btn btn-danger btn-sm" onClick={restoreNow}>
            Отменить
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setState(null)}
            aria-label="Скрыть"
          >
            ✕
          </button>
        </div>
      )}
      {children}
    </UndoContext.Provider>
  );
}

/* ========================= Сборка провайдеров ============================ */

export function AppProviders({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const bump = useCallback(() => setVersion((v) => v + 1), []);
  const versionValue = useMemo(() => ({ version, bump }), [version, bump]);

  return (
    <DataVersionContext.Provider value={versionValue}>
      <ToastProvider>
        <UndoProvider>{children}</UndoProvider>
      </ToastProvider>
    </DataVersionContext.Provider>
  );
}

export function useBump() {
  return useDataVersion().bump;
}

/* ============================ Примитивы ================================== */

export function Card({
  className = "",
  hover = false,
  style,
  children,
}: {
  className?: string;
  hover?: boolean;
  style?: CSSProperties;
  children: ReactNode;
}) {
  return (
    <article className={`card${hover ? " card-hover" : ""} ${className}`.trim()} style={style}>
      {children}
    </article>
  );
}

export function Badge({
  tone = "accent",
  children,
}: {
  tone?: "accent" | "muted" | "danger" | "warning" | "success";
  children: ReactNode;
}) {
  const toneClass = tone === "accent" ? "" : ` badge-${tone}`;
  return <span className={`badge${toneClass}`}>{children}</span>;
}

export function Chip({
  active = false,
  onClick,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  children: ReactNode;
}) {
  if (!onClick) {
    return <span className="chip chip-static">{children}</span>;
  }
  return (
    <button
      type="button"
      className={`chip${active ? " chip-active" : ""}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title,
  message,
  hint,
  confirmLabel = "Подтвердить",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: ReactNode;
  hint?: string;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal title={title} onClose={onCancel}>
      <p className="confirm-message">{message}</p>
      {hint && <p className="confirm-hint">{hint}</p>}
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Отмена
        </button>
        <button
          type="button"
          className={`btn ${danger ? "btn-danger" : "btn-primary"}`}
          onClick={onConfirm}
          disabled={busy}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export function EmptyState({
  icon = "📭",
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon" aria-hidden="true">
        {icon}
      </div>
      <div className="empty-title">{title}</div>
      {hint && <p className="dim">{hint}</p>}
      {action && <div className="mt-8">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="error-state" role="alert">
      <p>Не удалось получить данные от API.</p>
      <p className="state-hint">{message}</p>
      {hint && <p className="state-hint">{hint}</p>}
    </div>
  );
}

export function Skeleton() {
  return (
    <div className="skeleton" aria-hidden="true">
      <div className="skeleton-line" style={{ width: "55%" }} />
      <div className="skeleton-line" style={{ width: "85%" }} />
      <div className="skeleton-line" style={{ width: "40%" }} />
    </div>
  );
}

export function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid-cards" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} />
      ))}
    </div>
  );
}

export function Stepper({
  value,
  min = 0,
  onChange,
  disabled = false,
}: {
  value: number;
  min?: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <span className="stepper">
      <button
        type="button"
        className="stepper-btn"
        disabled={disabled || value <= min}
        onClick={() => onChange(value - 1)}
        aria-label="Убавить количество"
      >
        −
      </button>
      <span className="stepper-num">{value}</span>
      <button
        type="button"
        className="stepper-btn"
        disabled={disabled}
        onClick={() => onChange(value + 1)}
        aria-label="Прибавить количество"
      >
        +
      </button>
    </span>
  );
}

/* ====================== Пикер категории ================================== */

export const NEW_CATEGORY = "__new__";

/* Пикер категории форм: список существующих + «➕ Новая категория…»,
   при выборе которой появляется поле ввода. Итоговое имя вычисляет
   resolveCategory (совпадение без учёта регистра сводится к канону). */
export function CategoryPicker({
  categories,
  selected,
  typed,
  onSelected,
  onTyped,
}: {
  categories: string[];
  selected: string;
  typed: string;
  onSelected: (value: string) => void;
  onTyped: (value: string) => void;
}) {
  return (
    <Field label="Категория">
      <select
        className="select"
        value={selected}
        onChange={(event) => onSelected(event.target.value)}
      >
        <option value="">— без категории —</option>
        {categories.map((category) => (
          <option key={category} value={category}>
            {category}
          </option>
        ))}
        <option value={NEW_CATEGORY}>➕ Новая категория…</option>
      </select>
      {selected === NEW_CATEGORY && (
        <input
          className="input"
          placeholder="Название новой категории"
          aria-label="Название новой категории"
          autoFocus
          value={typed}
          onChange={(event) => onTyped(event.target.value)}
        />
      )}
    </Field>
  );
}

export function resolveCategory(selected: string, typed: string, existing: string[]): string {
  if (selected !== NEW_CATEGORY) return selected;
  const name = typed.trim();
  if (!name) return "";
  const canonical = existing.find((c) => c.toLowerCase() === name.toLowerCase());
  return canonical ?? name;
}
