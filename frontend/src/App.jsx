import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Cheques from "./pages/Cheques";
import Cartera from "./pages/Cartera";
import Retenciones from "./pages/Retenciones";
import Bancos from "./pages/Bancos";
import Flujo from "./pages/Flujo";
import Alertas from "./pages/Alertas";
import { useEffect, useState } from "react";
import Loader from "./components/Loader";
import { checkBackend } from "./lib/health";
import Reportes from "./pages/Reportes";
import { Toaster } from "sonner";

const Protected = ({ children }) => {
  const { user } = useAuth();

  if (user === undefined) {
    return (
      <div className="h-screen flex items-center justify-center text-slate-500">
        Cargando…
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return children;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="cheques" element={<Cheques />} />
        <Route path="cartera" element={<Cartera />} />
        <Route path="retenciones" element={<Retenciones />} />
        <Route path="bancos" element={<Bancos />} />
        <Route path="flujo" element={<Flujo />} />
        <Route path="alertas" element={<Alertas />} />
        <Route path="reportes" element={<Reportes />} />
      </Route>
    </Routes>
  );
}

function App() {
  const [ready, setReady] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("Inicializando sistema...");

  useEffect(() => {
  const init = async () => {
    setProgress(10);
    setMessage("Inicializando sistema...");

    await new Promise(r => setTimeout(r, 300));

    setProgress(30);
    setMessage("Conectando al servidor...");

    const backend = await checkBackend();
    if (!backend) {
      setMessage("No se pudo conectar con el servidor.");
      return;
    }

    setProgress(60);
    setMessage("Validando sesión...");

    await new Promise(r => setTimeout(r, 400));

    setProgress(80);
    setMessage("Cargando datos iniciales...");

    await new Promise(r => setTimeout(r, 400));

    setProgress(100);
    setMessage("Listo 🚀");

    setTimeout(() => setReady(true), 300);
  };

  init();
}, []);

  if (!ready) return <Loader message={message} progress={progress} />;


  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
          <Toaster richColors position="top-right" />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
