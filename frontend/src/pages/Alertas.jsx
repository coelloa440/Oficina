import { useEffect, useState } from "react";
import { api, fmtDate, fmtApiError } from "../lib/api";
import { useAuth, canWrite } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Mail, AlertTriangle, AlertCircle, Info, FileBarChart } from "lucide-react";
import { toast } from "sonner";

const iconByPriority = { high: AlertCircle, warning: AlertTriangle, info: Info };
const colorByPriority = {
  high: "border-red-500 bg-red-50 text-red-900",
  warning: "border-amber-500 bg-amber-50 text-amber-900",
  info: "border-blue-500 bg-blue-50 text-blue-900",
};

export default function Alertas() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [sending, setSending] = useState(false);
  const [sendingReport, setSendingReport] = useState(false);

  useEffect(() => {
    (async () => {
      const { data } = await api.get("/alertas");
      setItems(data);
    })();
  }, []);

  const filtered = items.filter(a => filter === "all" || a.priority === filter);
  const counts = {
    high: items.filter(i => i.priority === "high").length,
    warning: items.filter(i => i.priority === "warning").length,
    info: items.filter(i => i.priority === "info").length,
  };

  const sendEmail = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/alertas/enviar-email");
      if (data.sent) toast.success(`Email enviado con ${data.count} alertas`);
      else toast.info("Email configurado en modo desarrollo — revisa logs del servidor.");
    } catch (e) { toast.error(fmtApiError(e)); }
    finally { setSending(false); }
  };

  const sendWeeklyReport = async () => {
    setSendingReport(true);
    try {
      const { data } = await api.post("/reportes/semanal/enviar");
      if (data.sent) {
        toast.success(`Reporte ejecutivo enviado a ${data.delivered} destinatario(s)`);
      } else {
        toast.info(data.reason || "Reporte preparado pero no enviado (revisa logs).");
      }
    } catch (e) { toast.error(fmtApiError(e)); }
    finally { setSendingReport(false); }
  };

  return (
    <div className="space-y-6" data-testid="alertas-page">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-slate-900 tracking-tight">Centro de Alertas</h1>
          <p className="text-sm text-slate-500 mt-1">{items.length} alertas activas · Priorizadas por impacto financiero</p>
          <p className="text-xs text-slate-400 mt-1">📅 Reporte ejecutivo automático: <span className="font-medium text-slate-600">cada viernes 18:00 (hora Ecuador)</span></p>
        </div>
        {writable && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={sendWeeklyReport} disabled={sendingReport} variant="outline" className="w-full sm:w-auto">
              <FileBarChart className="w-4 h-4 mr-1.5" /> {sendingReport ? "Enviando…" : "Reporte ejecutivo"}
            </Button>
            <Button onClick={sendEmail} disabled={sending} className="bg-slate-900 hover:bg-slate-800 w-full sm:w-auto">
              <Mail className="w-4 h-4 mr-1.5" /> {sending ? "Enviando…" : "Enviar resumen"}
            </Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          ["Alta", "high", counts.high, "text-red-600 bg-red-50"],
          ["Advertencia", "warning", counts.warning, "text-amber-600 bg-amber-50"],
          ["Informativa", "info", counts.info, "text-blue-600 bg-blue-50"],
        ].map(([label, key, count, cls]) => (
          <button
            key={key}
            onClick={() => setFilter(filter === key ? "all" : key)}
            data-testid={`alert-filter-${key}`}
            className={`text-left p-4 rounded-md border transition-all ${filter === key ? "border-slate-900 shadow-sm" : "border-slate-200 bg-white hover:border-slate-300"}`}
          >
            <div className={`inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full ${cls}`}>{label}</div>
            <div className="mt-2 text-2xl sm:text-3xl font-display font-semibold text-slate-900 tabular-nums">{count}</div>
          </button>
        ))}
      </div>

      <div className="space-y-2.5">
        {filtered.length === 0 && (
          <div className="bg-white border border-slate-200 rounded-md p-10 text-center text-slate-400">
            Sin alertas en este filtro
          </div>
        )}
        {filtered.map(a => {
          const Icon = iconByPriority[a.priority] || Info;
          return (
            <div key={a.id} className={`border-l-4 rounded-xl p-4 shadow-sm ${colorByPriority[a.priority]}`}>
              <div className="flex flex-col sm:flex-row sm:items-start gap-3">
                <Icon className="w-5 h-5 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <div className="font-semibold">{a.titulo}</div>
                  <div className="text-sm opacity-80 mt-0.5">{a.detalle}</div>
                </div>
                <div className="text-xs opacity-70 sm:shrink-0">{fmtDate(a.fecha)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
