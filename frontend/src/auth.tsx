/* Контекст авторизации: текущий пользователь, вход/регистрация/выход.

   При монтировании запрашивается /api/auth/me (сессия в HttpOnly-cookie,
   поэтому состояние нельзя достать из localStorage — только от сервера).
   401 от /me — обычное состояние гостя: пользователь сбрасывается, и
   RequireAuth перенаправляет на форму входа. Прочие ошибки (нет связи
   с API, 5xx) не означают «не залогинен»: они сохраняются в authError,
   и вместо редиректа показывается экран сбоя с кнопкой «Повторить». */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ApiError,
  errorMessage,
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  UNAUTHORIZED_EVENT,
  type User,
} from "./api";

interface AuthValue {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  authError: string | null;
  retry: () => void;
  login: (login: string, password: string) => Promise<User>;
  register: (login: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue>({
  user: null,
  loading: true,
  isAdmin: false,
  authError: null,
  retry: () => {},
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
  const [authError, setAuthError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      setUser(me);
      setAuthError(null);
    } catch (err) {
      // Только 401 означает «сессии нет» (обычное состояние гостя).
      // Сетевой сбой или 5xx — не повод молча отправлять на форму входа:
      // текст ошибки сохраняется, RequireAuth показывает экран сбоя.
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        setAuthError(null);
      } else {
        setAuthError(errorMessage(err));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh, tick]);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const retry = useCallback(() => {
    setAuthError(null);
    setTick((t) => t + 1);
  }, []);

  const login = useCallback(async (loginName: string, password: string) => {
    const me = await apiLogin(loginName, password);
    setAuthError(null);
    setUser(me);
    return me;
  }, []);

  const register = useCallback(async (loginName: string, password: string) => {
    const me = await apiRegister(loginName, password);
    setAuthError(null);
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
    () => ({
      user,
      loading,
      isAdmin: user?.is_admin ?? false,
      authError,
      retry,
      login,
      register,
      logout,
    }),
    [user, loading, authError, retry, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
