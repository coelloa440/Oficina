import { useEffect, useMemo, useState } from "react";
import { api, money, fmtApiError, downloadExcel } from "../lib/api";
import { useAuth, canWrite } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "../components/ui/dialog";
import { Plus, Download, ChevronLeft, ChevronRight, Trash2, ArrowUp, ArrowDown } from "lucide-react";
import { toast } from "sonner";

const startOfWeek = (d) => {
  const date = new Date(d);
  const dow = date.getDay();
  const diff = dow === 0 ? -6 : 1 - dow;
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
};

const toISO = (d) => d.toISOString().slice(0, 10);

export default function Flujo() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [anchor, setAnchor] = useState(startOfWeek(new Date()));
  const [items, setItems] = useState([]);
  const [cheques, setCheques] = useState([]);
  const [bancos, setBancos] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    fecha: toISO(new Date()), tipo: "egreso", descripcion: "", monto: "", banco_id: "",
  });

  const weekDays = useMemo(() => {
    const arr = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(anchor);
      d.setDate(d.getDate() + i);
      arr.push(d);
    }
    return arr;
  }, [anchor]);

  const desde = toISO(weekDays[0]);
  const hasta = toISO(weekDays[6]);

  const load = async () => {
    const [{ data: flujoData }, { data: chequesData }] = await Promise.all([
      api.get(`/flujo?desde=${desde}&hasta=${hasta}`),
      api.get(`/cheques?estado=pendiente`),
    ]);

    setItems(flujoData);
    setCheques(
      chequesData
        .filter(c => c.fecha_cobro >= desde && c.fecha_cobro <= hasta)
        .map(c => ({
          id: `cheque-${c.id}`,
          fecha: c.fecha_cobro,
          tipo: "egreso",
          descripcion: `Cheque #${c.numero} · ${c.beneficiario}`,
          monto: c.valor,
          banco_id: c.banco_id,
          origen: "cheque",
        }))
    );
  };
  useEffect(() => { load(); }, [desde, hasta]);
  useEffect(() => {
    (async () => { setBancos((await api.get("/bancos")).data); })();
  }, []);

  const bancoMap = Object.fromEntries(bancos.map(b => [b.id, b]));
  const flujoCompleto = [...items, ...cheques];
  const byDay = Object.fromEntries(
    weekDays.map(d => [toISO(d), flujoCompleto.filter(x => x.fecha === toISO(d))])
  );
  const totalIngresos = flujoCompleto.filter(x => x.tipo === "ingreso").reduce((a, b) => a + b.monto, 0);
  const totalEgresos = flujoCompleto.filter(x => x.tipo === "egreso").reduce((a, b) => a + b.monto, 0);
  const addEntry = async () => {
    try {
      await api.post("/flujo", { ...form, monto: parseFloat(form.monto) });
      toast.success("Movimiento agregado");
      setOpen(false);
      setForm({ fecha: toISO(new Date()), tipo: "egreso", descripcion: "", monto: "", banco_id: "" });
      load();
    } catch (e) { toast.error(fmtApiError(e)); }
  };

  const delEntry = async (id) => {
    try { await api.delete(`/flujo/${id}`); load(); toast.success("Eliminado"); }
    catch (e) { toast.error(fmtApiError(e)); }
  };

  const shift = (n) => {
    const d = new Date(anchor);
    d.setDate(d.getDate() + n * 7);
    setAnchor(d);
  };

  return (
    <div className="space-y-6" data-testid="flujo-page">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-slate-900 tracking-tight">Flujo Semanal</h1>
          <p className="text-sm text-slate-500 mt-1">
            {weekDays[0].toLocaleDateString("es-EC", { day: "2-digit", month: "short" })} — {weekDays[6].toLocaleDateString("es-EC", { day: "2-digit", month: "short", year: "numeric" })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => shift(-1)} data-testid="prev-week-btn"><ChevronLeft className="w-4 h-4" /></Button>
          <Button variant="outline" onClick={() => setAnchor(startOfWeek(new Date()))}>Hoy</Button>
          <Button variant="outline" onClick={() => shift(1)} data-testid="next-week-btn"><ChevronRight className="w-4 h-4" /></Button>
          <Button variant="outline" onClick={() => downloadExcel("flujo")} data-testid="export-flujo-btn"><Download className="w-4 h-4 mr-1.5" /> Excel</Button>
          {writable && (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button className="bg-slate-900 hover:bg-slate-800 w-full sm:w-auto" data-testid="new-flujo-btn"><Plus className="w-4 h-4 mr-1.5" /> Movimiento</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Nuevo movimiento</DialogTitle></DialogHeader>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Fecha</Label><Input type="date" value={form.fecha} onChange={e=>setForm({...form, fecha: e.target.value})} /></div>
                  <div><Label>Tipo</Label>
                    <Select value={form.tipo} onValueChange={v => setForm({...form, tipo: v})}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ingreso">Ingreso</SelectItem>
                        <SelectItem value="egreso">Egreso</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="col-span-2"><Label>Descripción</Label><Input value={form.descripcion} onChange={e=>setForm({...form, descripcion: e.target.value})} data-testid="flujo-desc-input" /></div>
                  <div><Label>Monto</Label><Input type="number" step="0.01" value={form.monto} onChange={e=>setForm({...form, monto: e.target.value})} /></div>
                  <div><Label>Banco</Label>
                    <Select value={form.banco_id} onValueChange={v => setForm({...form, banco_id: v})}>
                      <SelectTrigger><SelectValue placeholder="Opcional" /></SelectTrigger>
                      <SelectContent>
                        {bancos.map(b => <SelectItem key={b.id} value={b.id}>{b.nombre}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter><Button onClick={addEntry} data-testid="flujo-save-btn">Guardar</Button></DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-white border border-slate-200 p-4 rounded-md">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Ingresos semana</div>
          <div className="text-xl sm:text-2xl font-display font-semibold tabular-nums text-emerald-700 mt-1">{money(totalIngresos)}</div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-md">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Egresos semana</div>
          <div className="text-xl sm:text-2xl font-display font-semibold tabular-nums text-rose-700 mt-1">{money(totalEgresos)}</div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-md">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Neto semana</div>
          <div className={`text-2xl font-display font-semibold tabular-nums mt-1 ${totalIngresos - totalEgresos >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{money(totalIngresos - totalEgresos)}</div>
        </div>
      </div>

      {/* Week grid */}
      <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
        {weekDays.map(d => {
          const iso = toISO(d);
          const today = toISO(new Date()) === iso;
          const entries = byDay[iso] || [];
          const dayIn = entries.filter(e => e.tipo === "ingreso").reduce((a, b) => a + b.monto, 0);
          const dayOut = entries.filter(e => e.tipo === "egreso").reduce((a, b) => a + b.monto, 0);
          return (
            <div key={iso} className={`bg-white border rounded-md p-3 min-h-[220px] ${today ? "border-emerald-400 ring-1 ring-emerald-100" : "border-slate-200"}`}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                    {d.toLocaleDateString("es-EC", { weekday: "short" })}
                  </div>
                  <div className={`text-xl font-display font-semibold ${today ? "text-emerald-700" : "text-slate-900"}`}>
                    {d.getDate()}
                  </div>
                </div>
                {(dayIn > 0 || dayOut > 0) && (
                  <div className="text-right text-[10px] tabular-nums">
                    <div className="text-emerald-700">+{money(dayIn)}</div>
                    <div className="text-rose-700">−{money(dayOut)}</div>
                  </div>
                )}
              </div>
              <div className="space-y-1.5">
                {entries.map(e => (
                  <div key={e.id} className={`text-xs p-2 rounded border ${e.tipo === "ingreso" ? "bg-emerald-50 border-emerald-100 text-emerald-900" : "bg-rose-50 border-rose-100 text-rose-900"}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1 font-medium">
                        {e.tipo === "ingreso" ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                        {e.descripcion}
                      </div>
                      {writable && e.origen !== "cheque" && (
                        <button onClick={() => delEntry(e.id)} className="opacity-40 hover:opacity-100">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                    <div className="mt-1 flex items-center justify-between">
                      <span className="opacity-70 truncate">{bancoMap[e.banco_id]?.nombre || ""}</span>
                      <span className="font-semibold tabular-nums">{money(e.monto)}</span>
                    </div>
                  </div>
                ))}
                {entries.length === 0 && <div className="text-[11px] text-slate-400 italic mt-6 text-center">Sin movimientos</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
