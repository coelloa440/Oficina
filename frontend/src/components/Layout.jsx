import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  LayoutDashboard,
  FileText,
  Users,
  Receipt,
  Landmark,
  CalendarRange,
  BellRing,
  FileBarChart,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { add } from "date-fns";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true, tid: "nav-dashboard" },
  { to: "/cheques", label: "Cheques", icon: FileText, tid: "nav-cheques" },
  { to: "/cartera", label: "Cartera", icon: Users, tid: "nav-cartera" },
  { to: "/retenciones", label: "Retenciones", icon: Receipt, tid: "nav-retenciones" },
  { to: "/bancos", label: "Bancos", icon: Landmark, tid: "nav-bancos" },
  { to: "/flujo", label: "Flujo Semanal", icon: CalendarRange, tid: "nav-flujo" },
  { to: "/alertas", label: "Alertas", icon: BellRing, tid: "nav-alertas" },
  { to: "/reportes", label: "Reportes", icon: FileBarChart, tid: "nav-reportes" },
];

const roleBadge = {
  admin: "bg-emerald-100 text-emerald-800 border-emerald-200",
  financiero: "bg-blue-100 text-blue-800 border-blue-200",
  consulta: "bg-slate-100 text-slate-700 border-slate-300",
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Sidebar */}
      <aside className="hidden lg:flex w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 border-r border-slate-800">
        <div className="px-5 py-6 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-display text-lg font-semibold text-white leading-none">
                Tesorería
              </div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mt-1">
                Control Financiero
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={item.tid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all ${
                  isActive
                    ? "bg-slate-800 text-white border-l-2 border-emerald-400 font-medium"
                    : "hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-slate-700 text-white flex items-center justify-center font-medium text-sm">
              {user?.name?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-white truncate" data-testid="user-name">
                {user?.name}
              </div>
              <div className="text-xs text-slate-400 truncate">{user?.email}</div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] uppercase tracking-wider font-semibold ${
                roleBadge[user?.role] || roleBadge.consulta
              }`}
              data-testid="user-role"
            >
              {user?.role}
            </span>
            <button
              onClick={handleLogout}
              data-testid="logout-btn"
              className="ml-auto text-slate-400 hover:text-white transition-colors"
              title="Cerrar sesión"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
      {/* Mobile Sidebar */}
        {open && (
          <div className="fixed inset-0 z-50 flex">
            {/* Fondo oscuro */}
            <div
              className="absolute inset-0 bg-black/50"
              onClick={() => setOpen(false)}
            />

            {/* Sidebar */}
            <aside className="relative w-64 bg-slate-900 text-slate-300 flex flex-col">
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
                <span className="text-white font-semibold">Menú</span>
                <button onClick={() => setOpen(false)}>
                  <X className="w-5 h-5 text-white" />
                </button>
              </div>

              <nav className="flex-1 p-3 space-y-1">
                {nav.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm hover:bg-slate-800"
                  >
                    <item.icon className="w-4 h-4" />
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </aside>
          </div>
        )}

      {/* Main */}
      <main className="flex-1 w-full">
        <div className="p-6 lg:p-8 max-w-[1600px] mx-auto">
          {/* Mobile header */}
            <div className="lg:hidden flex items-center justify-between mb-4">
              <button
                onClick={() => setOpen(true)}
                className="p-2 rounded-md bg-slate-800 text-white"
              >
                <Menu className="w-5 h-5" />
              </button>

              <span className="font-semibold text-slate-700">Tesorería</span>
            </div>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
