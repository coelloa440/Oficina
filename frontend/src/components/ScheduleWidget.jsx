import { useEffect, useState } from "react";
import { api, fmtApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "./ui/dialog";
import { Calendar, Clock, Settings2 } from "lucide-react";
import { toast } from "sonner";

const DAYS = [
  { v: 0, l: "Lunes" },
  { v: 1, l: "Martes" },
  { v: 2, l: "Miércoles" },
  { v: 3, l: "Jueves" },
  { v: 4, l: "Viernes" },
  { v: 5, l: "Sábado" },
  { v: 6, l: "Domingo" },
];

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = [0, 15, 30, 45];

const fmtNextRun = (iso) => {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-EC", {
      weekday: "long", day: "2-digit", month: "short",
      hour: "2-digit", minute: "2-digit",
    });
  } catch (e) { return iso; }
};

export default function ScheduleWidget() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [cfg, setCfg] = useState(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ day_of_week: 4, hour: 18, minute: 0 });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/reportes/semanal/config");
      setCfg(data);
      setDraft({ day_of_week: data.day_of_week, hour: data.hour, minute: data.minute });
    } catch (e) { /* ignore */ }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/reportes/semanal/config", draft);
      setCfg(data);
      toast.success(`Reporte reprogramado · ${data.day_label} ${String(data.hour).padStart(2, "0")}:${String(data.minute).padStart(2, "0")}`);
      setOpen(false);
    } catch (e) { toast.error(fmtApiError(e)); }
    finally { setSaving(false); }
  };

  if (!cfg) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-md p-5 lift" data-testid="schedule-widget">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-md bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Calendar className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.15em] text-slate-500 font-semibold">
              Reporte automático
            </div>
            <div className="font-display text-lg font-semibold text-slate-900 mt-0.5">
              {cfg.day_label} · {String(cfg.hour).padStart(2, "0")}:{String(cfg.minute).padStart(2, "0")}
            </div>
          </div>
        </div>
        {isAdmin && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <button className="p-1.5 text-slate-500 hover:bg-slate-100 rounded" data-testid="schedule-config-btn" title="Configurar">
                <Settings2 className="w-4 h-4" />
              </button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Programar reporte ejecutivo</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <p className="text-sm text-slate-600">
                  Define cuándo se enviará automáticamente el resumen semanal a admins y financieros.
                </p>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label className="text-xs uppercase tracking-wider text-slate-500">Día</Label>
                    <Select value={String(draft.day_of_week)} onValueChange={v => setDraft({...draft, day_of_week: Number(v)})}>
                      <SelectTrigger data-testid="day-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {DAYS.map(d => <SelectItem key={d.v} value={String(d.v)}>{d.l}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider text-slate-500">Hora</Label>
                    <Select value={String(draft.hour)} onValueChange={v => setDraft({...draft, hour: Number(v)})}>
                      <SelectTrigger data-testid="hour-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {HOURS.map(h => <SelectItem key={h} value={String(h)}>{String(h).padStart(2, "0")}h</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wider text-slate-500">Minutos</Label>
                    <Select value={String(draft.minute)} onValueChange={v => setDraft({...draft, minute: Number(v)})}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {MINUTES.map(m => <SelectItem key={m} value={String(m)}>:{String(m).padStart(2, "0")}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-md p-3 text-sm text-slate-700 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-slate-400" />
                  <span>
                    Cada <strong>{DAYS[draft.day_of_week].l}</strong> a las{" "}
                    <strong>{String(draft.hour).padStart(2, "0")}:{String(draft.minute).padStart(2, "0")}</strong> · zona Ecuador
                  </span>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
                <Button onClick={save} disabled={saving} className="bg-slate-900 hover:bg-slate-800" data-testid="schedule-save-btn">
                  {saving ? "Guardando…" : "Guardar"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>
      <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-2 text-xs text-slate-500">
        <Clock className="w-3.5 h-3.5" />
        <span>Próximo envío: <span className="font-medium text-slate-700 capitalize">{fmtNextRun(cfg.next_run)}</span></span>
      </div>
    </div>
  );
}
