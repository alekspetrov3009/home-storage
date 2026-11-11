import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  API_URL,
  deleteBox,
  fetchBox,
  fetchLocations,
  updateBox,
  type BoxPatch,
} from "../api";
import { useApi } from "../useApi";
import { useAuth } from "../auth";
import {
  Card,
  Chip,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  Skeleton,
  useBump,
  useToast,
  useUndo,
} from "../components/ui";
import ItemCard from "../components/ItemCard";

export default function BoxDetail() {
  const [params] = useSearchParams();
  const boxId = params.get("box") ?? "";

  // Без параметра — это не страница, а ошибка перехода: ведём к списку.
  if (!boxId) {
    return <RedirectToBoxes />;
  }

  return <BoxDetailById boxId={boxId} />;
}

function BoxDetailById({ boxId }: { boxId: string }) {
  const navigate = useNavigate();
  const bump = useBump();
  const toast = useToast();
  const undo = useUndo();
  const { isAdmin } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);

  const box = useApi(() => fetchBox(boxId), [boxId]);
  const locations = useApi(fetchLocations);

  useEffect(() => {
    if (!qrOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setQrOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [qrOpen]);

  const remove = useCallback(async () => {
    if (!box.data) return;
    setBusy(true);
    try {
      const entry = await deleteBox(box.data.id);
      bump();
      toast(`Ящик «${entry.name}» удалён — можно отменить`);
      undo.show(`ящик «${entry.name}»`, [entry]);
      setConfirming(false);
      navigate("/boxes");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setBusy(false);
    }
  }, [box.data, bump, toast, undo, navigate]);

  if (box.loading) {
    return (
      <div className="detail-grid">
        <Skeleton />
        <Skeleton />
      </div>
    );
  }

  if (box.error) {
    return (
      <>
        <ErrorState message={box.error} />
        <p className="mt-16">
          <Link to="/boxes">← Ко всем ящикам</Link>
        </p>
      </>
    );
  }

  const data = box.data!;

  return (
    <>
      <div className="page-header">
        <div>
          <p className="dim">
            <Link to="/boxes">Ящики</Link> / {data.name}
          </p>
          <h1>
            <span
              className="box-color-dot"
              style={{ background: data.color }}
              aria-hidden="true"
            />
            {data.name}
          </h1>
          <div className="detail-chips">
            {data.location_name ? (
              <Chip>{data.location_name}</Chip>
            ) : (
              <Chip>— без места хранения —</Chip>
            )}
            <Chip>
              {data.unit_count} ед. · {data.item_count} поз.
            </Chip>
          </div>
        </div>
        <div className="row">
          {isAdmin && (
            <>
              <button type="button" className="btn btn-outline" onClick={() => setEditing(true)}>
                ✏️ Редактировать
              </button>
              <button type="button" className="btn btn-danger" onClick={() => setConfirming(true)}>
                🗑 Удалить ящик
              </button>
            </>
          )}
        </div>
      </div>

      <div className="detail-grid section">
        <div className="section">
          {data.description && <p className="dim mb-16">{data.description}</p>}
          <h2 className="overline">Содержимое</h2>
          {data.items.length === 0 ? (
            <EmptyState
              icon="🧾"
              title="Ящик пуст"
              hint="Добавьте вещь — этот ящик будет выбран автоматически."
              action={
                isAdmin ? (
                  <Link to={`/add?box=${encodeURIComponent(data.id)}`} className="btn btn-primary">
                    ＋ Добавить вещь
                  </Link>
                ) : undefined
              }
            />
          ) : (
            <div className="grid-cards">
              {data.items.map((item) => (
                <ItemCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>

        <Card className="qr-card">
          <img
            className="qr-img"
            src={`${API_URL}/api/boxes/${encodeURIComponent(data.id)}/qr`}
            alt={`QR-код ящика «${data.name}»`}
            onClick={() => setQrOpen(true)}
          />
          <p className="dim">
            QR ведёт на эту страницу: откройте ссылку с телефона, чтобы посмотреть
            содержимое у полки.
          </p>
        </Card>
      </div>

      {qrOpen && (
        <div
          className="qr-overlay"
          onClick={() => setQrOpen(false)}
          role="dialog"
          aria-label="QR-код ящика"
        >
          <img
            src={`${API_URL}/api/boxes/${encodeURIComponent(data.id)}/qr`}
            alt={`QR-код ящика «${data.name}» (увеличенный)`}
          />
        </div>
      )}

      {editing && (
        <EditBoxModal
          box={data}
          locations={locations.data ?? []}
          onClose={() => setEditing(false)}
        />
      )}

      {confirming && (
        <ConfirmDialog
          title="Удалить ящик?"
          message={<>Ящик «{data.name}» уедет в корзину.</>}
          hint="Вещи останутся на складе «без ящика» и вернутся в него при восстановлении из корзины."
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

function EditBoxModal({
  box,
  locations,
  onClose,
}: {
  box: { id: string; name: string; location_id: string; description: string };
  locations: { id: string; name: string }[];
  onClose: () => void;
}) {
  const bump = useBump();
  const toast = useToast();

  const [name, setName] = useState(box.name);
  const [locationId, setLocationId] = useState(box.location_id);
  const [description, setDescription] = useState(box.description);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("Укажите название ящика.");
      return;
    }
    setBusy(true);
    setError(null);

    // PATCH только фактически изменённых полей.
    const patch: BoxPatch = {};
    if (name.trim() !== box.name) patch.name = name.trim();
    if (locationId !== box.location_id) patch.location_id = locationId;
    if (description !== box.description) patch.description = description;

    try {
      if (Object.keys(patch).length > 0) {
        await updateBox(box.id, patch);
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
    <Modal title="Редактировать ящик" onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Название">
          <input
            className="input"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoFocus
          />
        </Field>
        <Field label="Место хранения">
          <select
            className="select"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
          >
            <option value="">— без места хранения —</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Описание">
          <textarea
            className="textarea"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
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

function RedirectToBoxes() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/boxes", { replace: true });
  }, [navigate]);
  return null;
}
