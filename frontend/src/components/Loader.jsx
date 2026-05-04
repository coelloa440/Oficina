export default function Loader({ message, progress = 0 }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0f172a] px-6">
      <div className="w-full max-w-sm text-center text-white">
        
        {/* Logo */}
        <div className="mx-auto mb-6 w-24 h-24 rounded-[28px] overflow-hidden bg-white shadow-lg flex items-center justify-center">
        <img
            src="/pwa-192x192.png"
            alt="Finteck"
            className="w-full h-full object-cover"
        />
        </div>
        {/* Nombre */}
        <h1 className="text-2xl font-semibold">Finteck</h1>

        {/* Estado */}
        <p className="mt-2 text-sm text-slate-300">{message}</p>

        {/* Barra REAL */}
        <div className="mt-6 h-2 w-full bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-400 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Porcentaje */}
        <p className="mt-2 text-xs text-slate-400">{progress}%</p>

      </div>
    </div>
  );
}