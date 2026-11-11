/* Управление пользователями (вкладка «Пользователи» на /settings,
   только администратор).

   Список учётных записей, создание (логин, пароль, роль), редактирование
   (логин, сброс пароля, смена роли, блокировка) и удаление. Права
   проверяются на сервере (роутер закрыт require_admin) — здесь только
   удобный интерфейс. Последнего действующего администратора защищает
   сервер: 400 с понятным текстом показывается как ошибка формы. */

import { useState, type FormEvent } from "react";
import {
  createUser,
  deleteUser,
  fetchUsers,
  updateUser,
  type User,
  type UserRole,
} from "../api";
import { useApi } from "../useApi";
import {
  Badge,
  Card,
  ConfirmDialog,
  ErrorState,
  Field,
  Modal,
  Skeleton,
  useBump,
  useToast,
} from "../components/ui";

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "администратор",
  viewer: "просмотр",
};

export default function Users() {
  const users = useApi(fetchUsers);
  const bump = useBump();
  const toast = useToast();

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [deleting, setDeleting] = useState<User | null>(null);
  const [busyDelete, setBusyDelete] = useState(false);

  const confirmDelete = async () => {
    if (!deleting || busyDelete) return;
    setBusyDelete(true);
    try {
      await deleteUser(deleting.id);
      bump();
      toast(`Учётная запись «${deleting.login}» удалена`);
      setDeleting(null);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setDeleting(null);
    } finally {
      setBusyDelete(false);
    }
  };

  const list = users.data ?? [];

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Пользователи</h1>
          <p className="page-sub">
            Учётные записи и роли: администратор управляет складом, просмотр —
            только читает
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
          ＋ Новый пользователь
        </button>
      </div>

      {users.error && <ErrorState message={users.error} />}
      {users.loading && <Skeleton />}
      {users.data && (
        <Card className="section">
          <table className="users-table">
            <thead>
              <tr>
                <th>Логин</th>
                <th>Роль</th>
                <th>Статус</th>
                <th>Создан</th>
                <th aria-label="Действия" />
              </tr>
            </thead>
            <tbody>
              {list.map((user) => (
                <tr key={user.id}>
                  <td className="users-login">{user.login}</td>
                  <td>
                    <Badge tone={user.is_admin ? "accent" : "muted"}>
                      {ROLE_LABEL[user.role] ?? user.role}
                    </Badge>
                  </td>
                  <td>
                    {user.blocked ? (
                      <Badge tone="danger">заблокирован</Badge>
                    ) : (
                      <Badge tone="success">активен</Badge>
                    )}
                  </td>
                  <td className="dim num">{user.created_at.slice(0, 16)}</td>
                  <td className="users-actions">
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => setEditing(user)}
                      aria-label={`Редактировать «${user.login}»`}
                    >
                      ✏️
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      onClick={() => setDeleting(user)}
                      aria-label={`Удалить «${user.login}»`}
                    >
                      🗑
                    </button>
                  </td>
                </tr>
              ))}
              {list.length === 0 && (
                <tr>
                  <td colSpan={5} className="dim">
                    Пользователей нет — создайте первую учётную запись.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <UserFormModal
          title="Новый пользователь"
          onClose={() => setCreating(false)}
          onSubmit={async (payload) => {
            const user = await createUser(payload);
            setCreating(false);
            bump();
            toast(`Пользователь «${user.login}» создан`);
          }}
        />
      )}

      {editing && (
        <UserFormModal
          title={`Редактировать «${editing.login}»`}
          user={editing}
          onClose={() => setEditing(null)}
          onSubmit={async (payload) => {
            const user = await updateUser(editing.id, payload);
            setEditing(null);
            bump();
            toast(
              user.blocked
                ? `Учётная запись «${user.login}» заблокирована`
                : `Учётная запись «${user.login}» обновлена`,
            );
          }}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Удалить пользователя?"
          message={<>Учётная запись «{deleting.login}» будет удалена вместе с её сессиями.</>}
          hint="Вход под этим логином станет невозможен. Данные склада не затрагиваются."
          confirmLabel="Удалить"
          danger
          busy={busyDelete}
          onConfirm={() => void confirmDelete()}
          onCancel={() => setDeleting(null)}
        />
      )}
    </>
  );
}

interface UserFormValues {
  login: string;
  password: string;
  role: UserRole;
  blocked?: boolean;
}

function UserFormModal({
  title,
  user,
  onClose,
  onSubmit,
}: {
  title: string;
  user?: User;
  onClose: () => void;
  onSubmit: (payload: UserFormValues) => Promise<void>;
}) {
  const [login, setLogin] = useState(user?.login ?? "");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [role, setRole] = useState<UserRole>(user?.role ?? "viewer");
  const [blocked, setBlocked] = useState(user?.blocked ?? false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!login.trim()) {
      setError("Укажите логин.");
      return;
    }
    if (!user || password) {
      // При создании пароль обязателен; при редактировании пустой = не менять.
      if (password.length < 6) {
        setError("Пароль должен содержать минимум 6 символов.");
        return;
      }
      if (password !== repeat) {
        setError("Пароли не совпадают.");
        return;
      }
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        login: login.trim(),
        password,
        role,
        ...(user ? { blocked } : {}),
      });
    } catch (err) {
      // Тексты API — пользовательский контракт (занятый логин, последний
      // администратор, валидация) — показываются в форме как есть.
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit}>
        <Field label="Логин">
          <input
            className="input"
            value={login}
            onChange={(event) => setLogin(event.target.value)}
            autoComplete="off"
            autoFocus
          />
        </Field>
        <Field
          label={user ? "Новый пароль (пусто — не менять)" : "Пароль"}
        >
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
          />
        </Field>
        {(!user || password) && (
          <Field label="Повторите пароль">
            <input
              className="input"
              type="password"
              value={repeat}
              onChange={(event) => setRepeat(event.target.value)}
              autoComplete="new-password"
            />
          </Field>
        )}
        <Field label="Роль">
          <select
            className="select"
            value={role}
            onChange={(event) => setRole(event.target.value as UserRole)}
          >
            <option value="admin">администратор — полный доступ</option>
            <option value="viewer">просмотр — только чтение</option>
          </select>
        </Field>
        {user && (
          <label className="check-row">
            <input
              type="checkbox"
              checked={blocked}
              onChange={(event) => setBlocked(event.target.checked)}
            />
            <span>Заблокировать (вход и сессии закрываются)</span>
          </label>
        )}

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
