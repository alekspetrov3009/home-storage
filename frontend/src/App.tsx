import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import Layout from "./components/Layout";
import { useAuth } from "./auth";
import Dashboard from "./pages/Dashboard";
import Boxes from "./pages/Boxes";
import BoxDetail from "./pages/BoxDetail";
import Items from "./pages/Items";
import ItemDetail from "./pages/ItemDetail";
import AddItem from "./pages/AddItem";
import Locations from "./pages/Locations";
import Trash from "./pages/Trash";
import Search from "./pages/Search";
import Settings from "./pages/Settings";
import Login from "./pages/Login";

/* Страницы и данные склада закрыты на сервере; эти обёртки лишь вовремя
   перенаправляют неавторизованных на форму входа и уводят роль «просмотр»
   с админских маршрутов. Возвращённый после входа адрес — state.from. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return <div className="auth-loading" aria-label="Загрузка" />;
  }
  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="boxes" element={<Boxes />} />
        {/* Маршрут QR-кодов: именно /box с query ?box={id} */}
        <Route path="box" element={<BoxDetail />} />
        <Route path="items" element={<Items />} />
        <Route path="item/:id" element={<ItemDetail />} />
        <Route
          path="add"
          element={
            <RequireAdmin>
              <AddItem />
            </RequireAdmin>
          }
        />
        <Route path="locations" element={<Locations />} />
        <Route path="trash" element={<Trash />} />
        <Route path="search" element={<Search />} />
        {/* Настройки доступны любой роли: вкладка «Пароль» — всем,
            «Категории» и «Пользователи» скрываются в интерфейсе и закрыты
            на сервере (403) — проверка роли не доверяется фронту. */}
        <Route path="settings" element={<Settings />} />
        {/* Пользователи переехали отдельной вкладкой в настройки; старый
            адрес ведёт туда же (права прежние — только администратор). */}
        <Route
          path="users"
          element={
            <RequireAdmin>
              <Navigate to="/settings?tab=users" replace />
            </RequireAdmin>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
