import { createContext, useContext, useEffect, useState } from "react";
import { api, fmtApiError } from "../lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(undefined); // undefined = loading
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        setUser(data);
      } catch {
        setUser(null);
      }
    })();
  }, []);

  const login = async (email, password) => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      return true;
    } catch (e) {
      setError(fmtApiError(e));
      return false;
    }
  };

  const register = async (body) => {
    setError("");
    try {
      const { data } = await api.post("/auth/register", body);
      setUser(data);
      return true;
    } catch (e) {
      setError(fmtApiError(e));
      return false;
    }
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {}
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, error, setError }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

export const roleCan = (role, action) => {
  if (role === "admin") return true;
  if (role === "financiero") return action !== "delete-critical";
  return action === "view";
};

export const canWrite = (role) => role === "admin" || role === "financiero";
