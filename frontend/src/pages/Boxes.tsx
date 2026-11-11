import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createBox, fetchBoxes, fetchLocations, type Box } from "../api";
import { useApi } from "../useApi";
import { useAuth } from "../auth";
import {
  EmptyState,
  ErrorState,
  Field,
  Modal,
  SkeletonGrid,
  useBump,
  useToast,
} from "../components/ui";
import BoxCard from "../components/BoxCard";

const NO_LOCATION = "__no_location__";

interface BoxGroup {
  key: string;
  name: string;
  boxes: Box[];
}

export default function Boxes() {
  const boxes = useApi(fetchBoxes);
  const locations = useApi(fetchLocations);
  const { isAdmin } = useAuth();
  const [creating, setCreating] = useState(false);
  const bump = useBump();
  const toast = useToast();
  const navigate = useNavigate();

  const groups = useMemo<BoxGroup[]>(() => {
    const data = boxes.data;
    if (!data) return [];
    const byKey = new Map<string, BoxGroup>();
    for (const box of data) {
      const key = box.location_id || NO_LOCATION;
      const group = byKey.get(key) ?? {
        key,
        name: box.location_name ?? "Без места хранения",
        boxes: [],
      };
      group.boxes.push(box);
      byKey.set(key, group);
    }
    return [...byKey.values()].sort((a, b) => {
      if (a.key === NO_LOCATION) return 1;
      if (b.key === NO_LOCATION) return -1;
      return a.name.localeCompare(b.name, "ru");
    });
  }, [boxes.data]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Ящики</h1>
          <p className="page-sub">Хранилища внутри мест — по ним лежат вещи</p>
        </div>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            ＋ Создать ящик
          </button>
        )}
      </div>

      {boxes.error && <ErrorState message={boxes.error} />}
      {boxes.loading && <SkeletonGrid />}
      {boxes.data &&
        (boxes.data.length === 0 ? (
          <EmptyState
            icon="📦"
            title="Ящиков пока нет"
            hint="Создайте первый ящик и положите в него вещи."
            action={
              isAdmin ? (
                <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
                  ＋ Создать ящик
                </button>
              ) : undefined
            }
          />
        ) : (
          groups.map((group) => (
            <section key={group.key} className="section">
              <h2 className="overline">
                {group.name} · {group.boxes.length}
              </h2>
              <div className="grid-cards">
                {group.boxes.map((box) => (
                  <BoxCard key={box.id} box={box} />
                ))}
              </div>
            </section>
          ))
        ))}

      {creating && (
        <CreateBoxModal
          locations={locations.data ?? []}
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false);
            bump();
            toast("Ящик создан");
            navigate(`/box?box=${encodeURIComponent(id)}`);
          }}
        />
      )}
    </>
  );
}

function CreateBoxModal({
  locations,
  onClose,
  onCreated,
}: {
  locations: { id: string; name: string }[];
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [locationId, setLocationId] = useState("");
  const [description, setDescription] = useState("");
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
    try {
      const box = await createBox({
        name: name.trim(),
        location_id: locationId,
        description: description.trim(),
      });
      onCreated(box.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <Modal title="Новый ящик" onClose={onClose}>
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
            Создать
          </button>
        </div>
      </form>
    </Modal>
  );
}
