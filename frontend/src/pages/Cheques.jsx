import { useEffect, useState } from "react";
import { api, money, fmtDate, fmtApiError, downloadExcel } from "../lib/api";
import { useAuth, canWrite } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Download, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";

const estadoStyles = {
  cobrado: "bg-emerald-100 text-emerald-800 border-emerald-200",
  pendiente: "bg-amber-100 text-amber-900 border-amber-300",
  anulado: "bg-slate-100 text-slate-700 border-slate-300",
};

const emptyForm = {
  numero: "",
  valor: "",
  beneficiario: "",
  fecha_emision: new Date().toISOString().slice(0, 10),
  fecha_cobro: new Date().toISOString().slice(0, 10),
  motivo: "",
  estado: "pendiente",
  banco_id: "",
};

export default function Cheques() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [items, setItems] = useState([]);
  const [bancos, setBancos] = useState([]);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editId, setEditId] = useState(null);

  const load = async () => {
    const q = filter === "all" ? "" : `?estado=${filter}`;
    const { data } = await api.get(`/cheques${q}`);
    setItems(data);
  };

  useEffect(() => {
    (async () => {
      const b = await api.get("/bancos");
      setBancos(b.data);
    })();
  }, []);

  useEffect(() => { load(); }, [filter]);

  const save = async () => {
    try {
      const body = { ...form, valor: parseFloat(form.valor) };
      if (editId) await api.put(`/cheques/${editId}`, body);
      else await api.post("/cheques", body);
      toast.success(editId ? "Cheque actualizado" : "Cheque creado");
      setOpen(false);
      setForm(emptyForm);
      setEditId(null);
      load();
    } catch (e) {
      toast.error(fmtApiError(e));
    }
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar cheque?")) return;
    try {
      await api.delete(`/cheques/${id}`);
      toast.success("Cheque eliminado");
      load();
    } catch (e) { toast.error(fmtApiError(e)); }
  };

  const edit = (c) => {
    setForm({
      numero: c.numero, valor: c.valor, beneficiario: c.beneficiario,
      fecha_emision: c.fecha_emision, fecha_cobro: c.fecha_cobro,
      motivo: c.motivo || "", estado: c.estado, banco_id: c.banco_id,
    });
    setEditId(c.id);
    setOpen(true);
  };

  const totalPendiente = items.filter(i => i.estado === "pendiente").reduce((a, b) => a + b.valor, 0);

  return (
    <div className="space-y-6" data-testid="cheques-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-slate-900 tracking-tight">Cheques Emitidos</h1>
          <p className="text-sm text-slate-500 mt-1">
            Total pendiente de cobro: <span className="font-semibold text-slate-800 tabular-nums">{money(totalPendiente)}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadExcel("cheques")} data-testid="export-cheques-btn">
            <Download className="w-4 h-4 mr-1.5" /> Excel
          </Button>
          {writable && (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button onClick={() => { setForm(emptyForm); setEditId(null); }} className="bg-slate-900 hover:bg-slate-800" data-testid="new-cheque-btn">
                  <Plus className="w-4 h-4 mr-1.5" /> Nuevo cheque
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>{editId ? "Editar cheque" : "Nuevo cheque"}</DialogTitle>
                </DialogHeader>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Número</Label><Input value={form.numero} onChange={e=>setForm({...form, numero: e.target.value})} data-testid="cheque-numero-input" /></div>
                  <div><Label>Valor USD</Label><Input type="number" step="0.01" value={form.valor} onChange={e=>setForm({...form, valor: e.target.value})} data-testid="cheque-valor-input" /></div>
                  <div className="col-span-2"><Label>Beneficiario</Label><Input value={form.beneficiario} onChange={e=>setForm({...form, beneficiario: e.target.value})} data-testid="cheque-beneficiario-input" /></div>
                  <div><Label>Fecha emisión</Label><Input type="date" value={form.fecha_emision} onChange={e=>setForm({...form, fecha_emision: e.target.value})} /></div>
                  <div><Label>Fecha cobro</Label><Input type="date" value={form.fecha_cobro} onChange={e=>setForm({...form, fecha_cobro: e.target.value})} /></div>
                  <div><Label>Estado</Label>
                    <Select value={form.estado} onValueChange={v => setForm({...form, estado: v})}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="pendiente">Pendiente</SelectItem>
                        <SelectItem value="cobrado">Cobrado</SelectItem>
                        <SelectItem value="anulado">Anulado</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div><Label>Banco</Label>
                    <Select value={form.banco_id} onValueChange={v => setForm({...form, banco_id: v})}>
                      <SelectTrigger><SelectValue placeholder="Selecciona" /></SelectTrigger>
                      <SelectContent>
                        {bancos.map(b => <SelectItem key={b.id} value={b.id}>{b.nombre}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="col-span-2"><Label>Motivo</Label><Input value={form.motivo} onChange={e=>setForm({...form, motivo: e.target.value})} /></div>
                </div>
                <DialogFooter>
                  <Button onClick={save} data-testid="cheque-save-btn">{editId ? "Actualizar" : "Crear"}</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      <div className="flex gap-2">
        {["all", "pendiente", "cobrado", "anulado"].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            data-testid={`filter-${s}`}
            className={`px-3 py-1.5 text-xs rounded-full border uppercase tracking-wider font-medium transition-colors ${
              filter === s
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            {s === "all" ? "Todos" : s}
          </button>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              {["N°", "Beneficiario", "Emisión", "Cobro", "Días", "Valor", "Estado", ""].map((h) => (
                <th key={h} className="text-left py-3 px-4 text-[11px] font-bold uppercase tracking-wider text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr><td colSpan="8" className="py-10 text-center text-slate-400">Sin cheques registrados</td></tr>
            )}
            {items.map((c) => (
              <tr key={c.id} className="border-b border-slate-100 hover:bg-slate-50/60 transition-colors table-row-enter">
                <td className="py-3 px-4 font-medium text-slate-900">{c.numero}</td>
                <td className="py-3 px-4">{c.beneficiario}</td>
                <td className="py-3 px-4 text-slate-600">{fmtDate(c.fecha_emision)}</td>
                <td className="py-3 px-4 text-slate-600">{fmtDate(c.fecha_cobro)}</td>
                <td className={`py-3 px-4 tabular-nums ${c.dias_restantes < 0 ? "text-red-600" : c.dias_restantes <= 3 ? "text-amber-700 font-medium" : "text-slate-600"}`}>
                  {c.estado === "pendiente" ? (c.dias_restantes ?? "—") + "d" : "—"}
                </td>
                <td className="py-3 px-4 text-right tabular-nums font-medium">{money(c.valor)}</td>
                <td className="py-3 px-4">
                  <span
                    data-testid="cheque-status-badge"
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${estadoStyles[c.estado]}`}
                  >
                    {c.estado}
                  </span>
                </td>
                <td className="py-3 px-4">
                  {writable && (
                    <div className="flex gap-1 justify-end">
                      <button onClick={() => edit(c)} data-testid={`edit-cheque-${c.id}`} className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"><Pencil className="w-3.5 h-3.5" /></button>
                      {user?.role === "admin" && (
                        <button onClick={() => del(c.id)} className="p-1.5 text-red-500 hover:bg-red-50 rounded"><Trash2 className="w-3.5 h-3.5" /></button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
