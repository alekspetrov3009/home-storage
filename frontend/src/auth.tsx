/* Контекст авторизации: текущий пользователь, вход/регистрация/выход.

   При монтировании запрашивается /api/auth/me (сессия в HttpOnly-cookie,
   поэтому состояние нельзя достать из localStorage — только от сервера).
   Любой ответ 401 вне /api/auth/* сбрасывает пользователя, и RequireAuth
   перенаправляет на форму входа. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { fetchMe, login as apiLogin, logout as apiLogout, register as apiRegister, UNAUTHORIZED_EVENT, type User } from "./api";

interface AuthValue {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  login: (login: string, password: string) => Promise<User>;
  register: (login: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue>({
  user: null,
  loading: true,
  isAdmin: false,
  login: async () => {
    throw new Error("AuthProvider не установлен");
  },
  register: async () => {
    throw new Error("AuthProvider не установлен");
  },
  logout: async () => {},
});

export function useAuth(): AuthValue {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const login = useCallback(async (loginName: string, password: string) => {
    const me = await apiLogin(loginName, password);
    setUser(me);
    return me;
  }, []);

  const register = useCallback(async (loginName: string, password: string) => {
    const me = await apiRegister(loginName, password);
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ user, loading, isAdmin: user?.is_admin ?? false, login, register, logout }),
    [user, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
