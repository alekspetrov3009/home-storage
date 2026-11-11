import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { createItem, fetchBoxes, fetchCategories, type ItemInput } from "../api";
import { useApi } from "../useApi";
import {
  Card,
  CategoryPicker,
  Field,
  resolveCategory,
  useBump,
  useToast,
} from "../components/ui";

export default function AddItem() {
  const boxes = useApi(fetchBoxes);
  const categories = useApi(fetchCategories);
  const bump = useBump();
  const toast = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requestedBoxId = params.get("box") ?? "";

  const [name, setName] = useState("");
  const [boxId, setBoxId] = useState(requestedBoxId);
  const [quantity, setQuantity] = useState("1");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [typedCategory, setTypedCategory] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (requestedBoxId) setBoxId(requestedBoxId);
  }, [requestedBoxId]);

  useEffect(() => {
    if (boxId && boxes.data && !boxes.data.some((box) => box.id === boxId)) {
      setBoxId("");
    }
  }, [boxId, boxes.data]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Укажите название вещи.");
      return;
    }
    const qty = Number.parseInt(quantity, 10);
    if (Number.isNaN(qty) || qty < 1) {
      setError("Количество — целое число не меньше 1.");
      return;
    }
    const payload: ItemInput = {
      name: trimmed,
      box_id: boxId,
      quantity: qty,
      category: resolveCategory(selectedCategory, typedCategory, categories.data ?? []),
      notes: notes.trim(),
    };
    setBusy(true);
    setError(null);
    try {
      const created = await createItem(payload);
      bump();
      toast(`Вещь «${created.name}» добавлена`);
      if (payload.box_id) {
        navigate(`/box?box=${encodeURIComponent(payload.box_id)}`);
      } else {
        navigate(`/item/${encodeURIComponent(created.id)}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Добавить вещь</h1>
          <p className="page-sub">Новая запись на складе</p>
        </div>
      </div>

      <Card className="section" style={{ maxWidth: 560 }}>
        <form onSubmit={submit}>
          <Field label="Название">
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Например, отвёртка крестовая"
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
              {(boxes.data ?? []).map((box) => (
                <option key={box.id} value={box.id}>
                  {box.name}
                  {box.location_name ? ` — ${box.location_name}` : ""}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Количество (не меньше 1)">
            <input
              className="input num"
              inputMode="numeric"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />
          </Field>
          <CategoryPicker
            categories={categories.data ?? []}
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
              placeholder="Необязательно"
            />
          </Field>
          {error && <p className="inline-error">{error}</p>}
          <div className="row mt-8">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              ＋ Добавить
            </button>
          </div>
        </form>
      </Card>
    </>
  );
}
