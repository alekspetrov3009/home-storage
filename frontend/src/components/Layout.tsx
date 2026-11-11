import { useEffect, useState, type FormEvent } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { createBackup } from "../api";
import { useAuth } from "../auth";
import { useToast } from "./ui";
import { useTheme } from "../theme";

const NAV = [
  { to: "/", icon: "📊", label: "Обзор", end: true },
  { to: "/boxes", icon: "📦", label: "Ящики" },
  { to: "/items", icon: "🧾", label: "Вещи" },
  { to: "/locations", icon: "🗺", label: "Места" },
  { to: "/trash", icon: "🗑", label: "Корзина" },
];

const ADMIN_NAV = [
  { to: "/settings", icon: "⚙️", label: "Настройки" },
  { to: "/users", icon: "👥", label: "Пользователи" },
];

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const { theme, toggle } = useTheme();
  const { user, isAdmin, logout } = useAuth();

  useEffect(() => {
    setQuery(params.get("q") ?? "");
    setSidebarOpen(false);
  }, [params, location.pathname]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    navigate(`/search?q=${encodeURIComponent(q)}`);
  };

  const boxId = location.pathname === "/box" ? params.get("box") ?? "" : "";
  const addTarget = boxId ? `/add?box=${encodeURIComponent(boxId)}` : "/add";

  const makeBackup = async () => {
    try {
      const { path } = await createBackup();
      toast(`Копия создана: ${path}`);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  };

  const signOut = async () => {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  };

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar${sidebarOpen ? " open" : ""}`}>
        <NavLink to="/" className="sidebar-brand">
          📦 Домашний склад
        </NavLink>
        <nav className="nav" aria-label="Разделы">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
          {isAdmin &&
            ADMIN_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
            ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-box">
            <span className="user-login" title={user?.login}>
              {user?.login ?? ""}
            </span>
            <span className="user-role dim">
              {isAdmin ? "администратор" : "просмотр"}
            </span>
          </div>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void signOut()}
          >
            🚪 Выйти
          </button>
          <button type="button" className="btn btn-ghost" onClick={toggle}>
            {theme === "dark" ? "☀️ Светлая тема" : "🌙 Тёмная тема"}
          </button>
          {isAdmin && (
            <button type="button" className="btn btn-ghost" onClick={makeBackup}>
              💾 Резервная копия
            </button>
          )}
          <p className="sidebar-note dim">Данные — локальный Excel-файл.</p>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button
            type="button"
            className="btn btn-ghost mobile-only"
            onClick={() => setSidebarOpen((open) => !open)}
            aria-label="Меню"
          >
            ☰
          </button>
          <form className="topbar-search" onSubmit={submitSearch} role="search">
            <input
              className="input"
              type="search"
              placeholder="Поиск по складу…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label="Поиск"
            />
          </form>
          <div className="topbar-actions">
            {isAdmin && (
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  `btn btn-ghost${isActive ? " topbar-settings-active" : ""}`
                }
                aria-label="Настройки"
                title="Настройки"
              >
                ⚙️
              </NavLink>
            )}
            {isAdmin && (
              <NavLink to={addTarget} className="btn btn-primary">
                ＋<span className="add-text">&nbsp;Добавить</span>
              </NavLink>
            )}
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
