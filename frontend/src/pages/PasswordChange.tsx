/* Смена пароля собственной учётной записи (вкладка «Пароль» на /settings,
   доступна любой роли).

   Текущий пароль проверяется на сервере, новый хешируется (PBKDF2 —
   app.domain.passwords), поэтому в интерфейсе пароль нигде не хранится.
   После успешной смены сервер закрывает все остальные сессии пользователя
   (другие устройства разлогиниваются), текущая остаётся активной.
   Клиент повторяет серверную валидацию (минимальная длина, совпадение
   подтверждения) ради мгновенной обратной связи; тексты ошибок API
   показываются в форме как есть. Новые опции настроек добавляются
   отдельными секциями по той же схеме: оверлайн + Card. */

import { useState, type FormEvent } from "react";
import { changePassword, errorMessage } from "../api";
import { Card, Field, useToast } from "../components/ui";

/* Границы пароля — зеркало app.domain.users (PASSWORD_MIN/PASSWORD_MAX). */
const PASSWORD_MIN = 6;
const PASSWORD_MAX = 128;

export default function PasswordChange() {
  const toast = useToast();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!current) {
      setError("Укажите текущий пароль.");
      return;
    }
    if (next.length < PASSWORD_MIN || next.length > PASSWORD_MAX) {
      setError(`Новый пароль должен содержать от ${PASSWORD_MIN} до ${PASSWORD_MAX} символов.`);
      return;
    }
    if (next !== repeat) {
      setError("Пароли не совпадают.");
      return;
    }
    if (next === current) {
      setError("Новый пароль совпадает с текущим.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setRepeat("");
      // Остальные сессии закрыты на сервере, текущая остаётся активной.
      toast("Пароль изменён. Другие сеансы входа закрыты.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <p className="overline">Пароль</p>
      <Card className="section">
        <form onSubmit={submit}>
          <Field label="Текущий пароль">
            <input
              className="input"
              type="password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              autoComplete="current-password"
            />
          </Field>
          <Field label={`Новый пароль (от ${PASSWORD_MIN} символов)`}>
            <input
              className="input"
              type="password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Повторите новый пароль">
            <input
              className="input"
              type="password"
              value={repeat}
              onChange={(event) => setRepeat(event.target.value)}
              autoComplete="new-password"
            />
          </Field>

          {error && <p className="inline-error">{error}</p>}
          <div className="modal-actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={busy || !current || !next || !repeat}
            >
              Сменить пароль
            </button>
          </div>
        </form>
      </Card>
    </>
  );
}
