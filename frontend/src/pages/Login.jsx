import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { ShieldCheck, TrendingUp, Wallet2, BarChart3 } from "lucide-react";

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@finanzas.com");
  const [password, setPassword] = useState("admin123");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) navigate("/", { replace: true });

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    const ok = await login(email, password);
    setLoading(false);
    if (ok) navigate("/");
    else setErr("Credenciales inválidas. Verifica e intenta de nuevo.");
  };

  return (
    <div className="min-h-screen flex">
      {/* Left: form */}
      <div className="w-full lg:w-[480px] flex flex-col justify-between bg-white px-10 py-10">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-md bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-display text-lg font-semibold text-slate-900 leading-none">
              Control Financiero
            </div>
          </div>
        </div>

        <div>
          <h1 className="font-display text-4xl sm:text-5xl font-semibold text-slate-900 tracking-tight leading-tight">
            Una sola vista <br />
            para toda tu <em className="text-emerald-600 not-italic">empresa</em>.
          </h1>
          <p className="mt-4 text-slate-600 max-w-sm">
            Cheques, cartera, bancos, retenciones y flujo semanal — en tiempo real y sin Excel.
          </p>

          <form onSubmit={submit} className="mt-10 space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="email" className="text-xs uppercase tracking-wider text-slate-500">
                Correo
              </Label>
              <Input
                id="email"
                type="email"
                value=""
                onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
                className="mt-1.5"
                placeholder="tu@empresa.com"
                required
              />
            </div>
            <div>
              <Label htmlFor="password" className="text-xs uppercase tracking-wider text-slate-500">
                Contraseña
              </Label>
              <Input
                id="password"
                type="password"
                value=""
                onChange={(e) => setPassword(e.target.value)}
                data-testid="login-password-input"
                className="mt-1.5"
                required
              />
            </div>
            {err && (
              <div className="text-sm text-red-600" data-testid="login-error">
                {err}
              </div>
            )}
            <Button
              type="submit"
              disabled={loading}
              data-testid="login-submit-btn"
              className="w-full bg-slate-900 hover:bg-slate-800 text-white h-11"
            >
              {loading ? "Ingresando…" : "Ingresar al panel"}
            </Button>
          </form>

        </div>

        <div className="text-xs text-slate-400">
          © {new Date().getFullYear()} Sistema Integral de Control Financiero
        </div>
      </div>

      {/* Right: visual */}
      <div className="hidden lg:block flex-1 relative overflow-hidden">
        <img
          src="https://images.unsplash.com/photo-1761057999122-32c962e37408?crop=entropy&cs=srgb&fm=jpg&w=1600&q=80"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900/80 via-slate-900/60 to-emerald-900/60" />
        <div className="relative h-full flex flex-col justify-end p-12 text-white">
          <div className="grid grid-cols-2 gap-3 max-w-md mb-8">
            {[
              { icon: Wallet2, label: "Saldos en tiempo real" },
              { icon: TrendingUp, label: "Flujo semanal" },
              { icon: BarChart3, label: "Cartera & retenciones" },
              { icon: ShieldCheck, label: "Roles & auditoría" },
            ].map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-sm bg-white/10 backdrop-blur px-3 py-2 rounded-md">
                <f.icon className="w-4 h-4 text-emerald-300" /> {f.label}
              </div>
            ))}
          </div>
          <h2 className="font-display text-3xl font-semibold leading-tight max-w-lg">
            "Reemplazamos Excel por un panel único."
          </h2>
        </div>
      </div>
    </div>
  );
}
