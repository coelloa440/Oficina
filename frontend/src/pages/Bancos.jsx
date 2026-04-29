import { useEffect, useState } from "react";
import { api, money, fmtApiError, downloadExcel } from "../lib/api";
import { useAuth, canWrite } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "../components/ui/dialog";
import { Plus, Download, Pencil, Landmark } from "lucide-react";
import { toast } from "sonner";

const emptyForm = { nombre: "", saldo_efectivo: "", sobregiro_asignado: "", sobregiro_utilizado: "", color: "#0f766e" };

export default function Bancos() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [bancos, setBancos] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editId, setEditId] = useState(null);

  const load = async () => {
    const { data } = await api.get("/bancos");
    setBancos(data);
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      const body = {
        nombre: form.nombre,
        saldo_efectivo: parseFloat(form.saldo_efectivo || 0),
        sobregiro_asignado: parseFloat(form.sobregiro_asignado || 0),
        sobregiro_utilizado: parseFloat(form.sobregiro_utilizado || 0),
        color: form.color,
      };
      if (editId) await api.put(`/bancos/${editId}`, body);
      else await api.post("/bancos", body);
      toast.success("Banco guardado");
      setOpen(false); setForm(emptyForm); setEditId(null); load();
    } catch (e) { toast.error(fmtApiError(e)); }
  };

  const edit = (b) => {
    setForm({
      nombre: b.nombre, saldo_efectivo: b.saldo_efectivo,
      sobregiro_asignado: b.sobregiro_asignado, sobregiro_utilizado: b.sobregiro_utilizado,
      color: b.color || "#0f766e",
    });
    setEditId(b.id); setOpen(true);
  };

  const totales = {
    saldo: bancos.reduce((a, b) => a + b.saldo_efectivo, 0),
    disp: bancos.reduce((a, b) => a + b.disponible, 0),
    asig: bancos.reduce((a, b) => a + b.sobregiro_asignado, 0),
    uti: bancos.reduce((a, b) => a + b.sobregiro_utilizado, 0),
  };

  return (
    <div className="space-y-6" data-testid="bancos-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-slate-900 tracking-tight">Módulo Bancario</h1>
          <p className="text-sm text-slate-500 mt-1">Disponible = Saldo + Sobregiro asignado − Sobregiro utilizado</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadExcel("bancos")} data-testid="export-bancos-btn"><Download className="w-4 h-4 mr-1.5" /> Excel</Button>
          {writable && (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button onClick={() => { setForm(emptyForm); setEditId(null); }} className="bg-slate-900 hover:bg-slate-800" data-testid="new-banco-btn">
                  <Plus className="w-4 h-4 mr-1.5" /> Nuevo banco
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>{editId ? "Editar banco" : "Nuevo banco"}</DialogTitle></DialogHeader>
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2"><Label>Nombre</Label><Input value={form.nombre} onChange={e=>setForm({...form, nombre: e.target.value})} data-testid="banco-nombre-input" /></div>
                  <div><Label>Saldo efectivo</Label><Input type="number" step="0.01" value={form.saldo_efectivo} onChange={e=>setForm({...form, saldo_efectivo: e.target.value})} /></div>
                  <div><Label>Sobregiro asignado</Label><Input type="number" step="0.01" value={form.sobregiro_asignado} onChange={e=>setForm({...form, sobregiro_asignado: e.target.value})} /></div>
                  <div><Label>Sobregiro utilizado</Label><Input type="number" step="0.01" value={form.sobregiro_utilizado} onChange={e=>setForm({...form, sobregiro_utilizado: e.target.value})} /></div>
                  <div><Label>Color</Label><Input type="color" value={form.color} onChange={e=>setForm({...form, color: e.target.value})} /></div>
                </div>
                <DialogFooter><Button onClick={save} data-testid="banco-save-btn">Guardar</Button></DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Consolidated KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 p-4 rounded-md">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Saldo consolidado</div>
          <div className="text-2xl font-display font-semibold tabular-nums mt-1">{money(totales.saldo)}</div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-md">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Disponible real</div>
          <div className="text-2xl font-display font-semibold tabular-nums mt-1 text-emerald-700">{money(totales.disp)}</div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-md">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Sobregiro asignado</div>
          <div className="text-2xl font-display font-semibold tabular-nums mt-1">{money(totales.asig)}</div>
        </div>
        <div className="bg-white border border-slate-200 p-4 rounded-md">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Sobregiro utilizado</div>
          <div className="text-2xl font-display font-semibold tabular-nums mt-1">{money(totales.uti)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {bancos.map(b => {
          const pct = b.sobregiro_asignado > 0 ? Math.min(100, (b.sobregiro_utilizado / b.sobregiro_asignado) * 100) : 0;
          return (
            <div key={b.id} className="bg-white border border-slate-200 rounded-md p-5 lift relative overflow-hidden" data-testid={`banco-${b.id}`}>
              <div className="absolute top-0 left-0 right-0 h-1" style={{ background: b.color }} />
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-md flex items-center justify-center" style={{ background: `${b.color}18`, color: b.color }}>
                    <Landmark className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="font-semibold text-slate-900">{b.nombre}</div>
                    <div className="text-xs text-slate-500">Cuenta operativa</div>
                  </div>
                </div>
                {writable && (
                  <button onClick={() => edit(b)} className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"><Pencil className="w-4 h-4" /></button>
                )}
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Saldo efectivo</div>
                  <div className="font-semibold tabular-nums text-slate-900 mt-0.5">{money(b.saldo_efectivo)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Disponible</div>
                  <div className="font-semibold tabular-nums text-emerald-700 mt-0.5">{money(b.disponible)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Sobregiro asig.</div>
                  <div className="tabular-nums text-slate-700 mt-0.5">{money(b.sobregiro_asignado)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Sobregiro usado</div>
                  <div className="tabular-nums text-slate-700 mt-0.5">{money(b.sobregiro_utilizado)}</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                  <span>Uso sobregiro</span>
                  <span className="tabular-nums font-medium">{pct.toFixed(1)}%</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full transition-all ${pct > 80 ? "bg-red-500" : pct > 50 ? "bg-amber-500" : "bg-emerald-500"}`}
                    style={{ width: `${pct}%` }}
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
