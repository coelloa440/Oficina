export default function Loader({ message = "Inicializando sistema..." }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f8fafc] px-6">
      <div className="w-full max-w-sm text-center">
        <div className="mx-auto mb-6 relative w-24 h-24">
          <div className="absolute inset-0 rounded-3xl bg-emerald-500/20 blur-xl animate-pulse" />
          <div className="relative w-24 h-24 rounded-3xl bg-white border border-slate-200 shadow-lg flex items-center justify-center">
            <img
              src="/pwa-192x192.png"
              alt="Finteck"
              className="w-16 h-16 object-contain animate-[pulse_2s_ease-in-out_infinite]"
            />
          </div>
        </div>

        <h1 className="font-display text-2xl font-semibold text-slate-900">
          Finteck
        </h1>

        <p className="mt-2 text-sm font-medium text-slate-600">
          {message}
        </p>

        <div className="mt-6 h-2 w-full rounded-full bg-slate-200 overflow-hidden">
          <div className="h-full w-2/3 rounded-full bg-slate-900 animate-[loadingBar_1.6s_ease-in-out_infinite]" />
        </div>

        <p className="mt-4 text-xs text-slate-400">
          Preparando entorno financiero seguro...
        </p>
      </div>
    </div>
  );
}