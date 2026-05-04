import { useEffect, useState, useMemo } from "react";
import { api, money, fmtDate, fmtApiError, downloadExcel } from "../lib/api";
import { Plus, Download, Trash2, Pencil, Landmark, MoreVertical } from "lucide-react";
import { useAuth, canWrite } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { useAutoRefresh } from "../hooks/useAutoRefresh";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
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
  useAutoRefresh(load, 30000, [filter]);
  
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

  // Group by banco
  const grouped = useMemo(() => {
    const map = new Map();
    bancos.forEach(b => map.set(b.id, { banco: b, list: [] }));
    items.forEach(c => {
      if (!map.has(c.banco_id)) {
        map.set(c.banco_id, { banco: { id: c.banco_id, nombre: c.banco_nombre || "Sin banco", color: "#64748b" }, list: [] });
      }
      map.get(c.banco_id).list.push(c);
    });
    return Array.from(map.values()).filter(g => g.list.length > 0);
  }, [items, bancos]);

  return (
    <div className="space-y-6" data-testid="cheques-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-slate-900 tracking-tight">Cheques Emitidos</h1>
          <p className="text-sm text-slate-500 mt-1">
            Total pendiente de cobro: <span className="font-semibold text-slate-800 tabular-nums">{money(totalPendiente)}</span> · Agrupados por banco
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
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

      <div className="flex gap-2 overflow-x-auto pb-2">
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

      {grouped.length === 0 && (
        <div className="bg-white border border-slate-200 rounded-md p-12 text-center text-slate-400">
          Sin cheques en este filtro
        </div>
      )}

      {/* Grupos por banco */}
      <div className="space-y-6">
        {grouped.map(({ banco, list }) => {
          const totalGrupo = list.reduce((a, c) => a + c.valor, 0);
          const pendGrupo = list.filter(c => c.estado === "pendiente").reduce((a, c) => a + c.valor, 0);
          return (        
            <div key={banco.id}>
               {/* Vista móvil */}
                  <div className="md:hidden space-y-3">
                    <div
                      className="rounded-xl bg-slate-900 text-white p-4"
                      style={{ borderLeft: `5px solid ${banco.color || "#0f172a"}` }}
                    >
                      <div className="font-display text-lg font-semibold">{banco.nombre}</div>
                      <div className="text-xs text-slate-300 mt-1">
                        {list.length} cheque{list.length !== 1 ? "s" : ""} · Pendiente: {money(pendGrupo)}
                      </div>
                    </div>
                  {list.map((c) => (
                    <div key={c.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900">#{c.numero}</span>
                            <span className={`text-[11px] px-2 py-0.5 rounded-full border ${estadoStyles[c.estado]}`}>
                              {c.estado}
                            </span>
                          </div>

                          <p className="mt-2 text-sm text-slate-700 font-medium">
                            {c.beneficiario}
                          </p>
                        </div>

                        {writable && (
                          <div className="relative group">
                            <button className="p-2 rounded-full hover:bg-slate-100 text-slate-500">
                              <MoreVertical className="w-4 h-4" />
                            </button>

                            <div className="hidden group-focus-within:block group-hover:block absolute right-0 top-9 w-36 bg-white border border-slate-200 rounded-lg shadow-lg z-20 overflow-hidden">
                              <button
                                onClick={() => edit(c)}
                                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                              >
                                <Pencil className="w-4 h-4" />
                                Editar
                              </button>

                              {user?.role === "admin" && (
                                <button
                                  onClick={() => del(c.id)}
                                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                                >
                                  <Trash2 className="w-4 h-4" />
                                  Eliminar
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                        <div>
                          <p className="text-xs text-slate-400 uppercase font-semibold">Emisión</p>
                          <p className="text-slate-700">{fmtDate(c.fecha_emision)}</p>
                        </div>

                        <div>
                          <p className="text-xs text-slate-400 uppercase font-semibold">Cobro</p>
                          <p className="text-slate-700">{fmtDate(c.fecha_cobro)}</p>
                        </div>
                      </div>

                      <div className="mt-4 flex items-center justify-between">
                        <span className="text-xs text-slate-400 uppercase font-semibold">
                          Valor
                        </span>
                        <span className="text-lg font-bold text-slate-900 tabular-nums">
                          {money(c.valor)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Vista escritorio */}
                <div className="hidden md:block overflow-x-auto">
                  <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
                        <div
                          className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 bg-slate-50"
                          style={{ borderLeft: `4px solid ${banco.color || "#0f172a"}` }}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className="w-8 h-8 rounded-md flex items-center justify-center"
                              style={{ background: `${banco.color || "#0f172a"}18`, color: banco.color || "#0f172a" }}
                            >
                              <Landmark className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="font-display text-lg font-semibold text-slate-900 leading-none">{banco.nombre}</div>
                              <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mt-1">
                                {list.length} cheque{list.length !== 1 ? "s" : ""}
                              </div>
                            </div>
                          </div>
                          <div className="flex gap-6 text-right">
                            <div>
                              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Pendiente</div>
                              <div className="text-sm font-semibold tabular-nums text-amber-700 mt-0.5">{money(pendGrupo)}</div>
                            </div>
                            <div>
                              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Total</div>
                              <div className="text-sm font-semibold tabular-nums text-slate-900 mt-0.5">{money(totalGrupo)}</div>
                            </div>
                          </div>
                        </div>

                        <table className="w-full text-sm">
                          <thead className="bg-white border-b border-slate-100">
                            <tr>
                              {["N°", "Beneficiario", "Emisión", "Cobro", "Días", "Valor", "Estado", ""].map((h) => (
                                <th key={h} className="text-left py-2.5 px-4 text-[11px] font-bold uppercase tracking-wider text-slate-500">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {list.map((c) => (
                              <tr key={c.id} className="border-b border-slate-100 hover:bg-slate-50/60 transition-colors">
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
            </div>
          );
        })}
      </div>
    </div>
  );
}
