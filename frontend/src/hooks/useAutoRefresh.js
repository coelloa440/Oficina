import { useEffect, useRef, useState } from "react";

export function useAutoRefresh(callback, delay = 30000, deps = []) {
  const loadingRef = useRef(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    let isMounted = true;

    const safeRun = async () => {
      if (!isMounted) return;
      if (document.visibilityState !== "visible") return;
      if (loadingRef.current) return;

      loadingRef.current = true;
      try {
        await callback();
        setLastUpdated(new Date()); // 👈 CLAVE
      } finally {
        loadingRef.current = false;
      }
    };

    // Primera carga inmediata
    safeRun();

    const interval = setInterval(safeRun, delay);

    const onVisible = () => {
      if (document.visibilityState === "visible") {
        safeRun();
      }
    };

    document.addEventListener("visibilitychange", onVisible);

    return () => {
      isMounted = false;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, deps);

  return { lastUpdated }; // 👈 RETORNAMOS
}