import { useCallback, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  deleteItem,
  fetchBoxes,
  fetchCategories,
  fetchItem,
  formatDate,
  moveItem,
  updateItem,
  type ItemPatch,
} from "../api";
import { useApi } from "../useApi";
import { useAuth } from "../auth";
import {
  Badge,
  Card,
  CategoryPicker,
  Chip,
  ConfirmDialog,
  ErrorState,
  Field,
  Modal,
  NEW_CATEGORY,
  resolveCategory,
  Skeleton,
  Stepper,
  useBump,
  useToast,
  useUndo,
} from "../components/ui";

export default function ItemDetail() {
  const { id = "" } = useParams();
  const item = useApi(() => fetchItem(id), [id]);
  const boxes = useApi(fetchBoxes);
  const categories = useApi(fetchCategories);
  const { isAdmin } = useAuth();
  const bump = useBump();
  const toast = useToast();
  const undo = useUndo();
  const navigate = useNavigate();

  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const changeQuantity = useCallback(
    async (quantity: number) => {
      try {
        await updateItem(id, { quantity });
        bump();
        toast("Количество обновлено");
      } catch (err) {
        toast(err instanceof Error ? err.message : String(err), "error");
      }
    },
    [id, bump, toast],
  );

  const transfer = useCallback(
    async (targetBoxId: string) => {
      try {
        if (targetBoxId) {
          await moveItem(id, targetBoxId);
        } else {
          await updateItem(id, { box_id: "" });
        }
        bump();
        toast("Перенесено");
      } catch (err) {
        toast(err instanceof Error ? err.message : String(err), "error");
      }
    },
    [id, bump, toast],
  );

  const remove = useCallback(async () => {
    setBusy(true);
    try {
      const entry = await deleteItem(id);
      bump();
      toast(`Вещь «${entry.name}» удалена — можно отменить`);
      undo.show(`вещь «${entry.name}»`, [entry]);
      navigate("/items");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setBusy(false);
    }
  }, [id, bump, toast, undo, navigate]);

  if (item.loading) {
    return <Skeleton />;
  }

  if (item.error) {
    return (
      <>
        <ErrorState message={item.error} />
        <p className="mt-16">
          <Link to="/items">← Ко всем вещам</Link>
        </p>
      </>
    );
  }

  const data = item.data!;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="dim">
            <Link to="/items">Вещи</Link> / {data.name}
          </p>
          <h1>{data.name}</h1>
          <div className="detail-chips">
            {data.category && <Chip>{data.category}</Chip>}
            {data.box_label ? (
              <Chip>{data.box_label}</Chip>
            ) : (
              <Chip>— без ящика —</Chip>
            )}
          </div>
        </div>
        <div className="row">
          {isAdmin && (
            <>
              <button type="button" className="btn btn-outline" onClick={() => setEditing(true)}>
                ✏️ Редактировать
              </button>
              <button type="button" className="btn btn-danger" onClick={() => setConfirming(true)}>
                🗑 Удалить
              </button>
            </>
          )}
        </div>
      </div>

      <div className="detail-grid section">
        <Card>
          <div className="spread mb-16">
            <span className="overline" style={{ margin: 0 }}>
              Количество
            </span>
            {isAdmin ? (
              <Stepper value={data.quantity} onChange={changeQuantity} />
            ) : (
              <Badge>{data.quantity}</Badge>
            )}
          </div>

          {isAdmin && (
            <div className="field">
              <span className="field-label">Перенести в ящик</span>
              <select
                className="select"
                value={data.box_id}
                onChange={(event) => transfer(event.target.value)}
              >
                <option value="">— без ящика —</option>
                {(boxes.data ?? []).map((box) => (
                  <option key={box.id} value={box.id}>
                    {box.name}
                    {box.id === data.box_id ? " (сейчас здесь)" : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          {data.notes && (
            <>
              <span className="overline">Заметки</span>
              <p>{data.notes}</p>
            </>
          )}
        </Card>

        <Card>
          <dl className="kv-list">
            <div>
              <dt>Единиц</dt>
              <dd>
                <Badge>{data.quantity}</Badge>
              </dd>
            </div>
            <div>
              <dt>Категория</dt>
              <dd>{data.category || "—"}</dd>
            </div>
            <div>
              <dt>Ящик</dt>
              <dd>{data.box_label ?? "— без ящика —"}</dd>
            </div>
            <div>
              <dt>Обновлён</dt>
              <dd className="num">{formatDate(data.updated_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      {editing && (
        <EditItemModal
          item={data}
          boxes={boxes.data ?? []}
          categories={categories.data ?? []}
          onClose={() => setEditing(false)}
        />
      )}

      {confirming && (
        <ConfirmDialog
          title="Удалить вещь?"
          message={<>Вещь «{data.name}» уедет в корзину.</>}
          hint="Её можно восстановить из корзины в течение 30 дней."
          confirmLabel="Удалить"
          danger
          busy={busy}
          onConfirm={remove}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  );
}

function EditItemModal({
  item,
  boxes,
  categories,
  onClose,
}: {
  item: { id: string; name: string; box_id: string; quantity: number; category: string; notes: string };
  boxes: { id: string; name: string }[];
  categories: string[];
  onClose: () => void;
}) {
  const bump = useBump();
  const toast = useToast();

  const [name, setName] = useState(item.name);
  const [boxId, setBoxId] = useState(item.box_id);
  const [quantity, setQuantity] = useState(String(item.quantity));
  const [selectedCategory, setSelectedCategory] = useState(
    categories.includes(item.category) || item.category === "" ? item.category : NEW_CATEGORY,
  );
  const [typedCategory, setTypedCategory] = useState(
    categories.includes(item.category) || item.category === "" ? "" : item.category,
  );
  const [notes, setNotes] = useState(item.notes);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const resolved = resolveCategory(selectedCategory, typedCategory, categories);
    const qty = Number.parseInt(quantity, 10);
    if (!name.trim()) {
      setError("Укажите название вещи.");
      return;
    }
    if (Number.isNaN(qty) || qty < 0) {
      setError("Количество — целое число не меньше 0.");
      return;
    }
    setBusy(true);
    setError(null);

    // PATCH только фактически изменённых полей: каждое обновление
    // ставит штамп «Обновлён», лишних штампов быть не должно.
    const patch: ItemPatch = {};
    if (name.trim() !== item.name) patch.name = name.trim();
    if (qty !== item.quantity) patch.quantity = qty;
    if (resolved !== item.category) patch.category = resolved;
    if (notes !== item.notes) patch.notes = notes;
    if (boxId !== item.box_id) patch.box_id = boxId;

    try {
      if (Object.keys(patch).length > 0) {
        await updateItem(item.id, patch);
        bump();
        toast("Изменения сохранены");
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <Modal title="Редактировать вещь" onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Название">
          <input
            className="input"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
          />
        </Field>
        <Field label="Ящик">
          <select
            className="select"
            value={boxId}
            onChange={(event) => setBoxId(event.target.value)}
          >
            <option value="">— без ящика —</option>
            {boxes.map((box) => (
              <option key={box.id} value={box.id}>
                {box.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Количество (не меньше 0)">
          <input
            className="input num"
            inputMode="numeric"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </Field>
        <CategoryPicker
          categories={categories}
          selected={selectedCategory}
          typed={typedCategory}
          onSelected={setSelectedCategory}
          onTyped={setTypedCategory}
        />
        <Field label="Заметки">
          <textarea
            className="textarea"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </Field>
        {error && <p className="inline-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Сохранить
          </button>
        </div>
      </form>
    </Modal>
  );
}
