import { useEffect, useState } from "react";
import { api, money } from "../lib/api";
import ScheduleWidget from "../components/ScheduleWidget";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import {
  Wallet2,
  FileText,
  Users,
  Receipt,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

const COLORS = { cobrado: "#10b981", pendiente: "#f59e0b", anulado: "#94a3b8" };

const Kpi = ({ label, value, icon: Icon, tone = "slate", sub, tid }) => (
  <div
    data-testid={tid}
    className="bg-white border border-slate-200 rounded-md p-5 lift"
  >
    <div className="flex items-center justify-between">
      <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500">
        {label}
      </div>
      <div className={`w-8 h-8 rounded-md bg-${tone}-50 text-${tone}-600 flex items-center justify-center`}>
        <Icon className="w-4 h-4" />
      </div>
    </div>
    <div className="mt-2 text-2xl lg:text-3xl font-semibold font-display tabular-nums text-slate-900">
      {value}
    </div>
    {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
  </div>
);

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [alertas, setAlertas] = useState([]);

  useEffect(() => {
    (async () => {
      const [d, a] = await Promise.all([api.get("/dashboard"), api.get("/alertas")]);
      setData(d.data);
      setAlertas(a.data.slice(0, 5));
    })();
  }, []);

  if (!data) return <div className="text-slate-500">Cargando panel…</div>;

  const k = data.kpis;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-semibold text-slate-900 tracking-tight">
            Panel Gerencial
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Situación financiera consolidada · {new Date().toLocaleDateString("es-EC", { weekday: "long", day: "2-digit", month: "long", year: "numeric" })}
          </p>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <Kpi tid="kpi-saldo" label="Saldo Bancos" value={money(k.saldo_total_bancos)} icon={Wallet2} tone="emerald" />
        <Kpi tid="kpi-cheques" label="Cheques pendientes" value={money(k.total_cheques_pendientes)} icon={FileText} tone="amber" />
        <Kpi tid="kpi-cartera" label="Cartera pendiente" value={money(k.cartera_pendiente)} icon={Users} tone="blue" />
        <Kpi tid="kpi-retenciones" label="Retenciones" value={money(k.total_retenciones)} icon={Receipt} tone="purple" />
        <Kpi tid="kpi-disponible" label="Disponible real" value={money(k.disponible_real)} icon={TrendingUp} tone="slate" sub="Saldo + sobregiro disponible" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-md p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display text-lg font-semibold text-slate-900">Flujo próximos 7 días</h3>
            <div className="flex gap-3 text-xs">
              <span className="flex items-center gap-1.5 text-emerald-700"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Ingresos</span>
              <span className="flex items-center gap-1.5 text-rose-700"><span className="w-2 h-2 rounded-full bg-rose-500" /> Egresos</span>
            </div>
          </div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={data.flujo_7dias}>
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="dia" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip formatter={(v) => money(v)} />
                <Line type="monotone" dataKey="ingresos" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="egresos" stroke="#f43f5e" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-md p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Cheques por estado</h3>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={data.cheques_por_estado}
                  dataKey="cantidad"
                  nameKey="estado"
                  outerRadius={90}
                  innerRadius={55}
                  paddingAngle={2}
                >
                  {data.cheques_por_estado.map((entry, i) => (
                    <Cell key={i} fill={COLORS[entry.estado]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Cartera por cliente + Alertas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-md p-5">
          <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Cartera pendiente por cliente</h3>
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={data.cartera_por_cliente} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" stroke="#64748b" fontSize={12} />
                <YAxis type="category" dataKey="cliente" stroke="#64748b" fontSize={11} width={160} />
                <Tooltip formatter={(v) => money(v)} />
                <Bar dataKey="monto" fill="#0f766e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="space-y-4">
          <ScheduleWidget />
          <div className="bg-white border border-slate-200 rounded-md p-5">
            <h3 className="font-display text-lg font-semibold text-slate-900 mb-4">Alertas recientes</h3>
            <div className="space-y-2.5">
              {alertas.length === 0 && <p className="text-sm text-slate-500">Sin alertas activas.</p>}
              {alertas.map((a) => (
                <div
                  key={a.id}
                  className={`border-l-4 p-3 rounded-r-md text-sm ${
                    a.priority === "high"
                      ? "bg-red-50 border-red-500 text-red-900"
                      : a.priority === "warning"
                      ? "bg-amber-50 border-amber-500 text-amber-900"
                      : "bg-blue-50 border-blue-500 text-blue-900"
                  }`}
                >
                  <div className="font-medium">{a.titulo}</div>
                  <div className="text-xs opacity-80 mt-0.5">{a.detalle}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bancos summary row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.bancos.map((b) => {
          const pctSobregiro =
            b.sobregiro_asignado > 0
              ? Math.min(100, (b.sobregiro_utilizado / b.sobregiro_asignado) * 100)
              : 0;
          return (
            <div key={b.id} className="bg-white border border-slate-200 rounded-md p-5 lift" data-testid={`banco-card-${b.id}`}>
              <div className="flex items-center justify-between">
                <div className="font-medium text-slate-900">{b.nombre}</div>
                <div className="w-2 h-2 rounded-full" style={{ background: b.color }} />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wider">Saldo</div>
                  <div className="font-semibold tabular-nums text-slate-900">{money(b.saldo_efectivo)}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wider">Disponible</div>
                  <div className="font-semibold tabular-nums text-emerald-700">{money(b.disponible)}</div>
                </div>
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                  <span>Sobregiro {pctSobregiro.toFixed(0)}%</span>
                  <span className="tabular-nums">{money(b.sobregiro_utilizado)} / {money(b.sobregiro_asignado)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full ${pctSobregiro > 80 ? "bg-red-500" : pctSobregiro > 50 ? "bg-amber-500" : "bg-emerald-500"}`}
                    style={{ width: `${pctSobregiro}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
