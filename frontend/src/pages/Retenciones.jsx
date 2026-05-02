import { useEffect, useState } from "react";
import { api, money, fmtDate, downloadExcel } from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Search, Download } from "lucide-react";

export default function Retenciones() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      const { data } = await api.get("/retenciones");
      setItems(data);
    })();
  }, []);

  const filtered = items.filter(i => i.cliente_nombre.toLowerCase().includes(q.toLowerCase()));
  const total = filtered.reduce((a, b) => a + b.valor_retenido, 0);

  return (
    <div className="space-y-6" data-testid="retenciones-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-slate-900 tracking-tight">Estado de Retenciones</h1>
          <p className="text-sm text-slate-500 mt-1">
            Consolidado general: <span className="font-semibold text-slate-800 tabular-nums">{money(total)}</span>
          </p>
        </div>
        <Button variant="outline" onClick={() => downloadExcel("retenciones")} data-testid="export-retenciones-btn">
          <Download className="w-4 h-4 mr-1.5" /> Excel
        </Button>
      </div>

      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute top-1/2 -translate-y-1/2 left-3 text-slate-400" />
        <Input placeholder="Buscar por cliente…" value={q} onChange={e=>setQ(e.target.value)} className="pl-9" data-testid="retencion-search" />
      </div>

      <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              {["Cliente","Documento","Fecha","Valor Retenido"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-[11px] font-bold uppercase tracking-wider text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && <tr><td colSpan="4" className="py-10 text-center text-slate-400">Sin retenciones</td></tr>}
            {filtered.map(r => (
              <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50/60">
                <td className="py-3 px-4 font-medium text-slate-900">{r.cliente_nombre}</td>
                <td className="py-3 px-4 text-slate-600">{r.documento}</td>
                <td className="py-3 px-4 text-slate-600">{fmtDate(r.fecha)}</td>
                <td className="py-3 px-4 text-right tabular-nums font-semibold">{money(r.valor_retenido)}</td>
              </tr>
            ))}
          </tbody>
          {filtered.length > 0 && (
            <tfoot className="bg-slate-50 border-t border-slate-200">
              <tr>
                <td colSpan="3" className="py-3 px-4 text-right text-xs font-bold uppercase tracking-wider text-slate-500">Total general</td>
                <td className="py-3 px-4 text-right tabular-nums font-bold text-slate-900">{money(total)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
