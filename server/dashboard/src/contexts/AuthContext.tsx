import React, { createContext, useContext, useState, useCallback } from "react";
import { login as apiLogin } from "../api/client";

interface AuthCtx {
  isAuthenticated: boolean;
  login: (pw: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({} as AuthCtx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem("trilan_token")
  );

  const login = useCallback(async (password: string) => {
    const data = await apiLogin(password);
    localStorage.setItem("trilan_token", data.access_token);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("trilan_token");
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
