import { useState } from "react";
import { downloadExcel, downloadPDF, fmtApiError } from "../lib/api";
import {
  FileText,
  Users,
  Landmark,
  Receipt,
  CalendarRange,
  BarChart3,
  FileSpreadsheet,
  FileBarChart,
  Download,
} from "lucide-react";
import { toast } from "sonner";

const REPORTS = [
  {
    key: "cheques",
    title: "Estado de Cheques",
    desc: "Reporte completo de cheques emitidos agrupado por banco con estado, días restantes y totales.",
    icon: FileText,
    tone: { bg: "bg-blue-50", text: "text-blue-600", accent: "from-blue-500/10 to-blue-500/0" },
  },
  {
    key: "cartera",
    title: "Cartera por Cliente",
    desc: "Análisis detallado de cartera pendiente con subtotal, anticipos, retenciones y total neto.",
    icon: Users,
    tone: { bg: "bg-emerald-50", text: "text-emerald-600", accent: "from-emerald-500/10 to-emerald-500/0" },
  },
  {
    key: "bancos",
    title: "Movimientos Bancarios",
    desc: "Posición consolidada por banco: saldo, sobregiros asignado y usado, disponible real.",
    icon: Landmark,
    tone: { bg: "bg-amber-50", text: "text-amber-700", accent: "from-amber-500/10 to-amber-500/0" },
  },
  {
    key: "retenciones",
    title: "Consolidado Retenciones",
    desc: "Resumen total de retenciones aplicadas con detalle por cliente y documento.",
    icon: Receipt,
    tone: { bg: "bg-purple-50", text: "text-purple-600", accent: "from-purple-500/10 to-purple-500/0" },
  },
  {
    key: "flujo",
    title: "Flujo Semanal",
    desc: "Proyección semanal de ingresos y egresos con identificación de semanas críticas.",
    icon: CalendarRange,
    tone: { bg: "bg-teal-50", text: "text-teal-600", accent: "from-teal-500/10 to-teal-500/0" },
  },
  {
    key: "gerencial",
    title: "Reporte Gerencial",
    desc: "Dashboard ejecutivo con KPIs principales, posición bancaria y top clientes por cartera.",
    icon: BarChart3,
    tone: { bg: "bg-slate-100", text: "text-slate-700", accent: "from-slate-500/10 to-slate-500/0" },
    pdfOnly: true,
  },
];

export default function Reportes() {
  const [loading, setLoading] = useState({});

  const run = async (key, format) => {
    setLoading((l) => ({ ...l, [`${key}-${format}`]: true }));
    try {
      if (format === "pdf") await downloadPDF(key);
      else await downloadExcel(key);
      toast.success(`${format.toUpperCase()} generado`);
    } catch (e) {
      toast.error(fmtApiError(e));
    } finally {
      setLoading((l) => ({ ...l, [`${key}-${format}`]: false }));
    }
  };

  return (
    <div className="space-y-6" data-testid="reportes-page">
      <div>
        <h1 className="font-display text-3xl sm:text-4xl font-semibold text-slate-900 tracking-tight">
          Centro de Reportes
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Descarga reportes financieros en PDF listos para imprimir o en Excel editable.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {REPORTS.map((r) => (
          <div
            key={r.key}
            data-testid={`report-card-${r.key}`}
            className="relative bg-white border border-slate-200 rounded-md p-6 flex flex-col gap-4 overflow-hidden lift"
          >
            <div className={`absolute inset-x-0 top-0 h-20 bg-gradient-to-b ${r.tone.accent} pointer-events-none`} />

            <div className="relative flex items-start justify-between">
              <div className={`w-12 h-12 rounded-md flex items-center justify-center ${r.tone.bg} ${r.tone.text}`}>
                <r.icon className="w-6 h-6" strokeWidth={1.8} />
              </div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400 font-semibold">
                Reporte
              </div>
            </div>

            <div className="relative flex-1">
              <h3 className="font-display text-xl font-semibold text-slate-900 leading-snug">
                {r.title}
              </h3>
              <p className="text-sm text-slate-500 mt-2 leading-relaxed">{r.desc}</p>
            </div>

            <div className="relative pt-3 border-t border-slate-100 flex gap-2">
              <button
                onClick={() => run(r.key, "pdf")}
                disabled={!!loading[`${r.key}-pdf`]}
                data-testid={`pdf-${r.key}`}
                className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-rose-200 bg-rose-50 text-rose-700 text-xs font-semibold uppercase tracking-wider hover:bg-rose-100 transition-colors disabled:opacity-60"
              >
                <FileBarChart className="w-3.5 h-3.5" />
                {loading[`${r.key}-pdf`] ? "Generando…" : "PDF"}
              </button>
              {!r.pdfOnly && (
                <button
                  onClick={() => run(r.key, "excel")}
                  disabled={!!loading[`${r.key}-excel`]}
                  data-testid={`excel-${r.key}`}
                  className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-emerald-200 bg-emerald-50 text-emerald-700 text-xs font-semibold uppercase tracking-wider hover:bg-emerald-100 transition-colors disabled:opacity-60"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5" />
                  {loading[`${r.key}-excel`] ? "Generando…" : "Excel"}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-md p-5 flex items-start gap-3">
        <div className="w-9 h-9 rounded-md bg-white border border-slate-200 flex items-center justify-center text-slate-600 shrink-0">
          <Download className="w-4 h-4" />
        </div>
        <div>
          <div className="font-medium text-slate-900">Sobre los reportes</div>
          <p className="text-sm text-slate-600 mt-1 leading-relaxed">
            Los PDFs usan formato A4 listo para impresión con resumen total al pie. Los Excel incluyen todas las columnas originales para análisis y pivoteo.
            El <strong>Reporte Gerencial</strong> combina KPIs, posición bancaria y top clientes en un solo documento ejecutivo.
          </p>
        </div>
      </div>
    </div>
  );
}
