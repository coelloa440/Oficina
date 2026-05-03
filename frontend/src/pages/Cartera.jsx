import { useEffect, useState } from "react";
import { api, money, fmtDate, fmtApiError, downloadExcel } from "../lib/api";
import { useAuth, canWrite } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Download, Trash2, Pencil, UserPlus, MoreVertical } from "lucide-react";
import { toast } from "sonner";

const estadoStyles = {
  recibida: "bg-emerald-100 text-emerald-800 border-emerald-200",
  pendiente: "bg-amber-100 text-amber-900 border-amber-300",
};

const emptyFact = {
  cliente_id: "",
  numero_documento: "",
  fecha_emision: new Date().toISOString().slice(0, 10),
  estado: "pendiente",
  subtotal: "",
  anticipos: "0",
  retencion: "0",
};

export default function Cartera() {
  const { user } = useAuth();
  const writable = canWrite(user?.role);
  const [facturas, setFacturas] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [cliFilter, setCliFilter] = useState("all");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyFact);
  const [editId, setEditId] = useState(null);

  const [cliOpen, setCliOpen] = useState(false);
  const [cliForm, setCliForm] = useState({ nombre: "", ruc: "", contacto: "", email: "" });

  const load = async () => {
    const params = new URLSearchParams();
    if (cliFilter !== "all") params.set("cliente_id", cliFilter);
    if (desde) params.set("desde", desde);
    if (hasta) params.set("hasta", hasta);
    const { data } = await api.get(`/facturas?${params}`);
    setFacturas(data);
  };

  const loadClientes = async () => {
    const c = await api.get("/clientes");
    setClientes(c.data);
  };

  useEffect(() => { loadClientes(); }, []);
  useEffect(() => { load(); }, [cliFilter, desde, hasta]);

  const totalBySubtract = facturas.filter(f => f.estado === "pendiente").reduce((a, f) => a + f.total, 0);

  const save = async () => {
    try {
      const body = {
        ...form,
        subtotal: parseFloat(form.subtotal),
        anticipos: parseFloat(form.anticipos || 0),
        retencion: parseFloat(form.retencion || 0),
      };
      if (editId) await api.put(`/facturas/${editId}`, body);
      else await api.post("/facturas", body);
      toast.success(editId ? "Factura actualizada" : "Factura creada");
      setOpen(false); setForm(emptyFact); setEditId(null); load();
    } catch (e) { toast.error(fmtApiError(e)); }
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar factura?")) return;
    try { await api.delete(`/facturas/${id}`); toast.success("Eliminada"); load(); }
    catch (e) { toast.error(fmtApiError(e)); }
  };

  const edit = (f) => {
    setForm({
      cliente_id: f.cliente_id, numero_documento: f.numero_documento,
      fecha_emision: f.fecha_emision, estado: f.estado,
      subtotal: f.subtotal, anticipos: f.anticipos, retencion: f.retencion,
    });
    setEditId(f.id); setOpen(true);
  };

  const saveCli = async () => {
    try {
      await api.post("/clientes", cliForm);
      toast.success("Cliente creado");
      setCliOpen(false); setCliForm({ nombre: "", ruc: "", contacto: "", email: "" });
      loadClientes();
    } catch (e) { toast.error(fmtApiError(e)); }
  };

  const cliMap = Object.fromEntries(clientes.map(c => [c.id, c.nombre]));
  const totPreview = (parseFloat(form.subtotal || 0) - parseFloat(form.anticipos || 0) - parseFloat(form.retencion || 0));

  return (
    <div className="space-y-6" data-testid="cartera-page">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
         <h1 className="font-display text-3xl sm:text-4xl font-semibold text-slate-900 tracking-tight leading-tight">Cartera de Clientes</h1>
          <p className="text-sm text-slate-500 mt-1">
            Total pendiente: <span className="font-semibold text-slate-800 tabular-nums">{money(totalBySubtract)}</span> · Fórmula Total = Subtotal − Anticipos − Retenciones
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => downloadExcel("cartera")} data-testid="export-cartera-btn"><Download className="w-4 h-4 mr-1.5" /> Excel</Button>
          {writable && (
            <>
              <Dialog open={cliOpen} onOpenChange={setCliOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" data-testid="new-cliente-btn"><UserPlus className="w-4 h-4 mr-1.5" /> Cliente</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>Nuevo cliente</DialogTitle></DialogHeader>
                  <div className="space-y-3">
                    <div><Label>Nombre *</Label><Input value={cliForm.nombre} onChange={e=>setCliForm({...cliForm, nombre: e.target.value})} data-testid="cliente-nombre-input" /></div>
                    <div><Label>RUC</Label><Input value={cliForm.ruc} onChange={e=>setCliForm({...cliForm, ruc: e.target.value})} /></div>
                    <div><Label>Contacto</Label><Input value={cliForm.contacto} onChange={e=>setCliForm({...cliForm, contacto: e.target.value})} /></div>
                    <div><Label>Email</Label><Input value={cliForm.email} onChange={e=>setCliForm({...cliForm, email: e.target.value})} /></div>
                  </div>
                  <DialogFooter><Button onClick={saveCli} data-testid="cliente-save-btn">Guardar</Button></DialogFooter>
                </DialogContent>
              </Dialog>

              <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                  <Button onClick={() => { setForm(emptyFact); setEditId(null); }} className="bg-slate-900 hover:bg-slate-800" data-testid="new-factura-btn">
                    <Plus className="w-4 h-4 mr-1.5" /> Nueva factura
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>{editId ? "Editar" : "Nueva"} factura</DialogTitle></DialogHeader>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2"><Label>Cliente</Label>
                      <Select value={form.cliente_id} onValueChange={v => setForm({...form, cliente_id: v})}>
                        <SelectTrigger data-testid="factura-cliente-trigger"><SelectValue placeholder="Selecciona" /></SelectTrigger>
                        <SelectContent>
                          {clientes.map(c => <SelectItem key={c.id} value={c.id}>{c.nombre}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div><Label>N° Documento</Label><Input value={form.numero_documento} onChange={e=>setForm({...form, numero_documento: e.target.value})} data-testid="factura-doc-input" /></div>
                    <div><Label>Fecha</Label><Input type="date" value={form.fecha_emision} onChange={e=>setForm({...form, fecha_emision: e.target.value})} /></div>
                    <div><Label>Estado</Label>
                      <Select value={form.estado} onValueChange={v => setForm({...form, estado: v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="pendiente">Pendiente</SelectItem>
                          <SelectItem value="recibida">Recibida</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div><Label>Subtotal</Label><Input type="number" step="0.01" value={form.subtotal} onChange={e=>setForm({...form, subtotal: e.target.value})} data-testid="factura-subtotal-input" /></div>
                    <div><Label>Anticipos</Label><Input type="number" step="0.01" value={form.anticipos} onChange={e=>setForm({...form, anticipos: e.target.value})} /></div>
                    <div><Label>Retención</Label><Input type="number" step="0.01" value={form.retencion} onChange={e=>setForm({...form, retencion: e.target.value})} /></div>
                    <div className="col-span-2 bg-slate-50 border border-slate-200 rounded-md px-4 py-3 text-sm">
                      Total calculado: <span className="font-bold tabular-nums text-slate-900">{money(totPreview)}</span>
                    </div>
                  </div>
                  <DialogFooter><Button onClick={save} data-testid="factura-save-btn">{editId ? "Actualizar" : "Crear"}</Button></DialogFooter>
                </DialogContent>
              </Dialog>
            </>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-end">
        <div>
          <Label className="text-xs uppercase tracking-wider text-slate-500">Cliente</Label>
          <Select value={cliFilter} onValueChange={setCliFilter}>
            <SelectTrigger className="w-64" data-testid="filter-cliente"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los clientes</SelectItem>
              {clientes.map(c => <SelectItem key={c.id} value={c.id}>{c.nombre}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs uppercase tracking-wider text-slate-500">Desde</Label>
          <Input type="date" value={desde} onChange={e=>setDesde(e.target.value)} className="w-40" />
        </div>
        <div>
          <Label className="text-xs uppercase tracking-wider text-slate-500">Hasta</Label>
          <Input type="date" value={hasta} onChange={e=>setHasta(e.target.value)} className="w-40" />
        </div>
      </div>

      {/* Vista móvil */}
        <div className="md:hidden space-y-3">
          {facturas.length === 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400">
              Sin facturas
            </div>
          )}

          {facturas.map((f) => (
            <div key={f.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900">{f.numero_documento}</span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full border ${estadoStyles[f.estado]}`}>
                      {f.estado}
                    </span>
                  </div>

                  <p className="mt-2 text-sm text-slate-700 font-medium">
                    {cliMap[f.cliente_id] || "—"}
                  </p>
                </div>

                {writable && (
                  <div className="relative group">
                    <button className="p-2 rounded-full hover:bg-slate-100 text-slate-500">
                      <MoreVertical className="w-4 h-4" />
                    </button>

                    <div className="hidden group-focus-within:block group-hover:block absolute right-0 top-9 w-36 bg-white border border-slate-200 rounded-lg shadow-lg z-20 overflow-hidden">
                      <button
                        onClick={() => edit(f)}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                      >
                        <Pencil className="w-4 h-4" />
                        Editar
                      </button>

                      {user?.role === "admin" && (
                        <button
                          onClick={() => del(f.id)}
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
                  <p className="text-xs text-slate-400 uppercase font-semibold">Fecha</p>
                  <p className="text-slate-700">{fmtDate(f.fecha_emision)}</p>
                </div>

                <div>
                  <p className="text-xs text-slate-400 uppercase font-semibold">Subtotal</p>
                  <p className="text-slate-700">{money(f.subtotal)}</p>
                </div>

                <div>
                  <p className="text-xs text-slate-400 uppercase font-semibold">Anticipos</p>
                  <p className="text-slate-700">−{money(f.anticipos)}</p>
                </div>

                <div>
                  <p className="text-xs text-slate-400 uppercase font-semibold">Retención</p>
                  <p className="text-slate-700">−{money(f.retencion)}</p>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
                <span className="text-xs text-slate-400 uppercase font-semibold">Total</span>
                <span className="text-lg font-bold text-slate-900 tabular-nums">
                  {money(f.total)}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Vista escritorio */}
        <div className="hidden md:block bg-white border border-slate-200 rounded-md overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]">
            <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      {["Cliente","Documento","Fecha","Subtotal","Anticipos","Retención","Total","Estado",""].map(h => (
                        <th key={h} className="text-left py-3 px-4 text-[11px] font-bold uppercase tracking-wider text-slate-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {facturas.length === 0 && <tr><td colSpan="9" className="py-10 text-center text-slate-400">Sin facturas</td></tr>}
                    {facturas.map(f => (
                      <tr key={f.id} className="border-b border-slate-100 hover:bg-slate-50/60">
                        <td className="py-3 px-4 font-medium text-slate-900">{cliMap[f.cliente_id] || "—"}</td>
                        <td className="py-3 px-4 text-slate-600">{f.numero_documento}</td>
                        <td className="py-3 px-4 text-slate-600">{fmtDate(f.fecha_emision)}</td>
                        <td className="py-3 px-4 text-right tabular-nums">{money(f.subtotal)}</td>
                        <td className="py-3 px-4 text-right tabular-nums text-slate-500">−{money(f.anticipos)}</td>
                        <td className="py-3 px-4 text-right tabular-nums text-slate-500">−{money(f.retencion)}</td>
                        <td className="py-3 px-4 text-right tabular-nums font-semibold">{money(f.total)}</td>
                        <td className="py-3 px-4">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${estadoStyles[f.estado]}`}>{f.estado}</span>
                        </td>
                        <td className="py-3 px-4">
                          {writable && (
                            <div className="flex gap-1 justify-end">
                              <button onClick={() => edit(f)} className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"><Pencil className="w-3.5 h-3.5" /></button>
                              {user?.role === "admin" && (
                                <button onClick={() => del(f.id)} className="p-1.5 text-red-500 hover:bg-red-50 rounded"><Trash2 className="w-3.5 h-3.5" /></button>
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
