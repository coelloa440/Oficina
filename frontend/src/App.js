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
