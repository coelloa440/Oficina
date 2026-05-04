import axios from "axios";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export const checkBackend = async () => {
  try {
    await axios.get(`${BACKEND_URL}/api/auth/me`, {
      timeout: 5000,
      withCredentials: true,
    });

    return true;
  } catch (e) {
    // Si el backend responde 401, significa que está vivo,
    // solo que el usuario no está autenticado.
    if (e.response && e.response.status === 401) {
      return true;
    }

    return false;
  }
};