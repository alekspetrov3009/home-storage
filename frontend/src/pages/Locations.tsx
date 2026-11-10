import { useState, type FormEvent } from "react";
import {
  createLocation,
  deleteLocation,
  fetchLocations,
  updateLocation,
  type Location,
  type LocationPatch,
} from "../api";
import { useApi } from "../useApi";
import {
  Badge,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  SkeletonGrid,
  useBump,
  useToast,
  useUndo,
} from "../components/ui";

export default function Locations() {
  const locations = useApi(fetchLocations);
  const bump = useBump();
  const toast = useToast();
  const undo = useUndo();

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const [pending, setPending] = useState<Location | null>(null);
  const [busy, setBusy] = useState(false);

  const remove = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      const entry = await deleteLocation(pending.id);
      bump();
      toast(`Место «${entry.name}» удалено — можно отменить`);
      undo.show(`место «${entry.name}»`, [entry]);
      setPending(null);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setPending(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Места хранения</h1>
          <p className="page-sub">Комнаты и зоны, где стоят ящики</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
          ＋ Добавить место
        </button>
      </div>

      {locations.error && <ErrorState message={locations.error} />}
      {locations.loading && <SkeletonGrid />}
      {locations.data &&
        (locations.data.length === 0 ? (
          <EmptyState
            icon="🗺"
            title="Мест пока нет"
            hint="Создайте первое место — например, «Кладовка» или «Балкон»."
            action={
              <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
                ＋ Добавить место
              </button>
            }
          />
        ) : (
          <div className="grid-cards">
            {locations.data.map((location) => (
              <Card key={location.id} hover className="box-card">
                <div className="box-card-title">
                  <span>{location.name}</span>
                  <Badge tone="muted">
                    {location.box_count} ящ.
                  </Badge>
                </div>
                {location.description && <p className="dim">{location.description}</p>}
                <div className="row mt-8">
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => setEditing(location)}
                  >
                    ✏️ Редактировать
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    onClick={() => setPending(location)}
                  >
                    🗑 Удалить
                  </button>
                </div>
              </Card>
            ))}
          </div>
        ))}

      {creating && (
        <CreateLocationModal
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            bump();
            toast("Место создано");
          }}
        />
      )}

      {editing && (
        <EditLocationModal
          location={editing}
          onClose={() => setEditing(null)}
        />
      )}

      {pending && (
        <ConfirmDialog
          title="Удалить место?"
          message={<>Место «{pending.name}» уедет в корзину.</>}
          hint="Ящики останутся на складе «без места хранения» и вернутся сюда при восстановлении места из корзины."
          confirmLabel="Удалить"
          danger
          busy={busy}
          onConfirm={remove}
          onCancel={() => setPending(null)}
        />
      )}
    </>
  );
}

function EditLocationModal({
  location,
  onClose,
}: {
  location: Location;
  onClose: () => void;
}) {
  const bump = useBump();
  const toast = useToast();

  const [name, setName] = useState(location.name);
  const [description, setDescription] = useState(location.description);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("Укажите название места.");
      return;
    }
    setBusy(true);
    setError(null);

    // PATCH только фактически изменённых полей.
    const patch: LocationPatch = {};
    if (name.trim() !== location.name) patch.name = name.trim();
    if (description !== location.description) patch.description = description;

    try {
      if (Object.keys(patch).length > 0) {
        await updateLocation(location.id, patch);
        bump();
        toast("Изменения сохранены");
      }
      onClose();
    } catch (err) {
      // 409 (переименование в существующее место) — пользовательский контракт.
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <Modal title="Редактировать место" onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Название" error={error}>
          <input
            className="input"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
          />
        </Field>
        <Field label="Описание">
          <textarea
            className="textarea"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
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

function CreateLocationModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("Укажите название места.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createLocation({ name: name.trim(), description: description.trim() });
      onCreated();
    } catch (err) {
      // 409 (дубликат имени) и прочие тексты — пользовательский контракт.
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <Modal title="Новое место хранения" onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Название" error={error}>
          <input
            className="input"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Кладовка"
            autoFocus
          />
        </Field>
        <Field label="Описание">
          <textarea
            className="textarea"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Создать
          </button>
        </div>
      </form>
    </Modal>
  );
}
