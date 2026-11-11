import { useEffect, useRef, useState, type FormEvent } from "react";
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

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
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
    setUserMenuOpen(false);
  }, [params, location.pathname]);

  // Клик мимо меню пользователя или Esc — закрываем меню.
  useEffect(() => {
    if (!userMenuOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setUserMenuOpen(false);
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [userMenuOpen]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    navigate(`/search?q=${encodeURIComponent(q)}`);
  };

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
        </nav>
        <div className="sidebar-footer">
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
            <div className="user-menu" ref={userMenuRef}>
              <button
                type="button"
                className={`user-menu-trigger${userMenuOpen ? " open" : ""}`}
                onClick={() => setUserMenuOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                title={user?.login}
              >
                <span className="user-avatar" aria-hidden="true">
                  {(user?.login ?? "?").slice(0, 1).toUpperCase()}
                </span>
                <span className="user-menu-name">{user?.login ?? ""}</span>
                <span className="user-menu-caret" aria-hidden="true">
                  ▾
                </span>
              </button>
              {userMenuOpen && (
                <div className="user-menu-pop" role="menu" aria-label="Меню пользователя">
                  <div className="user-menu-head">
                    <span className="user-menu-login">{user?.login ?? ""}</span>
                    <span className="user-menu-role">
                      {isAdmin ? "администратор" : "просмотр"}
                    </span>
                  </div>
                  <p className="user-menu-perms">
                    {isAdmin
                      ? "Полный доступ: создание и правка вещей, ящиков и мест, управление пользователями."
                      : "Только чтение: просмотр склада без возможности изменений."}
                  </p>
                  {/* Настройки — любая роль: своя вкладка «Пароль» есть у всех. */}
                  <button
                    type="button"
                    className="btn btn-ghost user-menu-settings"
                    onClick={() => {
                      setUserMenuOpen(false);
                      navigate("/settings");
                    }}
                  >
                    ⚙️ Настройки
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost user-menu-logout"
                    onClick={() => void signOut()}
                  >
                    🚪 Выйти
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
