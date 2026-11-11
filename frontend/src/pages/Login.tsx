/* Страница входа и регистрации (/login) — единственный маршрут без Layout.

   Успешный вход/регистрация возвращают на исходную страницу (state.from).
   Регистрация сразу выполняет вход; новая учётная запись получает роль
   «просмотр», а самая первая на пустом складе — «администратор».
   Переключатель «Регистрация» показывается только когда сервер разрешает
   самостоятельную регистрацию (REGISTRATION_MODE, поле registration_open
   публичного GET /api/health); при закрытой регистрации учётные записи
   создаёт администратор. Пока health не загружен, показываем только вход —
   безопасная сторона. */

import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage, fetchHealth } from "../api";
import { useAuth } from "../auth";

type Mode = "login" | "register";

export default function Login() {
  const { user, loading, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from =
    (location.state as { from?: string } | null)?.from ?? "/";

  const [mode, setMode] = useState<Mode>("login");
  const [registrationOpen, setRegistrationOpen] = useState(false);
  const [loginName, setLoginName] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchHealth().then(
      (health) => {
        if (!cancelled) setRegistrationOpen(health.registration_open);
      },
      () => {
        /* health недоступен — регистрация не показывается, вход работает */
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  if (!loading && user) {
    return <Navigate to={from} replace />;
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const name = loginName.trim();
    if (!name || !password) {
      setError("Введите логин и пароль.");
      return;
    }
    if (mode === "register") {
      if (password !== repeat) {
        setError("Пароли не совпадают.");
        return;
      }
      if (password.length < 6) {
        setError("Пароль должен содержать минимум 6 символов.");
        return;
      }
    }
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(name, password);
      } else {
        await register(name, password);
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand" aria-hidden="true">
          📦
        </div>
        <h1>Домашний склад</h1>
        <p className="dim">
          {mode === "login"
            ? "Войдите, чтобы открыть склад"
            : "Регистрация новой учётной записи"}
        </p>

        {registrationOpen && (
          <div className="segmented auth-tabs" role="tablist" aria-label="Вход или регистрация">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className={`segmented-btn${mode === "login" ? " active" : ""}`}
              onClick={() => {
                setMode("login");
                setError(null);
              }}
            >
              Вход
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "register"}
              className={`segmented-btn${mode === "register" ? " active" : ""}`}
              onClick={() => {
                setMode("register");
                setError(null);
              }}
            >
              Регистрация
            </button>
          </div>
        )}

        <form onSubmit={submit}>
          <label className="field">
            <span className="field-label">Логин</span>
            <input
              className="input"
              value={loginName}
              onChange={(event) => setLoginName(event.target.value)}
              autoComplete="username"
              autoFocus
            />
          </label>
          <label className="field">
            <span className="field-label">Пароль</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>
          {mode === "register" && (
            <label className="field">
              <span className="field-label">Повторите пароль</span>
              <input
                className="input"
                type="password"
                value={repeat}
                onChange={(event) => setRepeat(event.target.value)}
                autoComplete="new-password"
              />
            </label>
          )}

          {error && <p className="inline-error">{error}</p>}

          <button type="submit" className="btn btn-primary auth-submit" disabled={busy}>
            {mode === "login" ? "Войти" : "Зарегистрироваться"}
          </button>
        </form>

        {mode === "register" && (
          <p className="dim auth-note">
            Новая учётная запись может только просматривать склад. Первая
            учётная запись на пустом складе становится администратором.
          </p>
        )}
      </div>
    </div>
  );
}
