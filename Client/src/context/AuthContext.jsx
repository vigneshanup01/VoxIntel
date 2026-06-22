import { createContext, useCallback, useContext, useEffect, useState } from "react";

import * as authApi from "../api/auth";
import { TOKEN_KEY } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .getCurrentUser()
      .then(setUser)
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const { access_token } = await authApi.login({ email, password });
    localStorage.setItem(TOKEN_KEY, access_token);
    const currentUser = await authApi.getCurrentUser();
    setUser(currentUser);
  }, []);

  const signup = useCallback(async (email, password, fullName) => {
    const { user: newUser, token } = await authApi.signup({ email, password, fullName });
    localStorage.setItem(TOKEN_KEY, token.access_token);
    setUser(newUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
