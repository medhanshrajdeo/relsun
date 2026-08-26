"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  type AuthUser,
  fetchCurrentUser,
  login as apiLogin,
  logout as apiLogout,
  setAuthToken,
  setUnauthorizedHandler,
} from "./api";

const TOKEN_STORAGE_KEY = "relsun:auth-token";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const clear = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAuthToken(null);
    setUser(null);
  }, []);

  // On mount: restore a previously-issued session token, if any, and
  // validate it against the backend rather than trusting it blindly — an
  // expired/revoked token (e.g. logged out from another tab) should bounce
  // straight to /login instead of showing a stale "logged in" state.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clear();
      router.replace("/login");
    });

    const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    setAuthToken(stored);
    fetchCurrentUser()
      .then(setUser)
      .catch(() => clear())
      .finally(() => setLoading(false));

    return () => setUnauthorizedHandler(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (username: string, password: string) => {
    const { token, user: loggedInUser } = await apiLogin(username, password);
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    setAuthToken(token);
    setUser(loggedInUser);
  };

  const logout = () => {
    apiLogout();
    clear();
    router.replace("/login");
  };

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
