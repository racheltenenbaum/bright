import { createContext, useContext, useState } from "react";
import { identify, resetAnalytics } from "../analytics";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("user");
    const parsed = saved ? JSON.parse(saved) : null;
    if (parsed) identify(parsed);
    return parsed;
  });

  function login(userData, token) {
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
    localStorage.setItem("token", token);
    identify(userData);
  }

  function logout() {
    setUser(null);
    localStorage.removeItem("user");
    localStorage.removeItem("token");
    resetAnalytics();
  }

  function updateUser(patch) {
    setUser((prev) => {
      const updated = { ...prev, ...patch };
      localStorage.setItem("user", JSON.stringify(updated));
      return updated;
    });
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, updateUser, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
