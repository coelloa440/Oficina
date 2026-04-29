# Sistema Integral de Control Financiero y Cartera · PRD

## Problema original
Reemplazar el uso manual de múltiples archivos Excel con una plataforma centralizada para administrar y visualizar en tiempo real: cheques emitidos, cartera de clientes, estado de retenciones, flujo semanal de pagos, saldos bancarios, sobregiros, cuentas por cobrar y disponibilidad financiera proyectada.

## Arquitectura
- **Backend**: FastAPI (Python) + MongoDB (motor). JWT en cookies httpOnly, bcrypt para contraseñas.
- **Frontend**: React 19 + React Router + shadcn/ui + Recharts + Tailwind.
- **Integración email**: Resend (opcional; en stub mode cuando falta API key).
- **Export**: openpyxl para Excel (xlsx).

## User personas / Roles
- **admin** — acceso total, puede crear/editar/eliminar
- **financiero** — crear/editar, no elimina
- **consulta** — solo lectura

## Core requirements (estático)
1. Cheques con estados cobrado/pendiente/anulado + colores + días restantes automático
2. Cartera con fórmula Total = Subtotal − Anticipos − Retenciones
3. Retenciones consolidadas derivadas de cartera
4. Bancos con Disponible = Saldo + Sobregiro asignado − Sobregiro utilizado
5. Flujo semanal tipo calendario (ingresos/egresos)
6. Dashboard gerencial con KPIs + Recharts
7. Alertas automáticas priorizadas (alta/advertencia/info)
8. Exportación Excel por módulo
9. Seguridad por roles (admin/financiero/consulta)

## Implementado (29-abril-2026 · MVP v1)
- ✅ Auth JWT (login/register/logout/me) con cookies httpOnly + rol-based guards
- ✅ Seed idempotente de usuarios (admin/financiero/consulta) + credentials en `/app/memory/test_credentials.md`
- ✅ Seed demo: 3 bancos (Guayaquil/Bolivariano/Pichincha), 6 clientes, 10 cheques, 12 facturas, 9 movimientos de flujo
- ✅ Módulo Cheques: CRUD + filtros + días restantes + descuento/reposición automática del saldo bancario al cambiar estado
- ✅ Módulo Cartera: CRUD facturas + clientes + filtros por cliente/fecha + fórmula Total en vivo
- ✅ Módulo Retenciones: vista consolidada con búsqueda por cliente
- ✅ Módulo Bancos: tarjetas con color, progreso de sobregiro, disponible real, CRUD
- ✅ Módulo Flujo Semanal: calendario 7 días con navegación semana-a-semana, totales ingreso/egreso/neto
- ✅ Dashboard: 5 KPIs + pie chart cheques por estado + line chart flujo 7 días + bar chart cartera por cliente + resumen bancos + alertas recientes
- ✅ Alertas: cheques próximos, sobregiro alto, saldo bajo, facturas vencidas — priorizadas + filtro + envío por email (stub si falta RESEND_API_KEY)
- ✅ Export Excel para cheques, cartera, retenciones, bancos, flujo
- ✅ Testing 31/31 backend tests passed (100%)
- ✅ Diseño: archetype "Swiss & High-Contrast" adaptado a finanzas corporativas, fuente display Fraunces + cuerpo IBM Plex Sans, sidebar dark navy, colores semánticos verde/amarillo/gris para estados de cheques

## Backlog prioritizado

### P0 — críticos no implementados aún
_Ninguno — MVP completo_

### P1 — mejoras de robustez
- Exportación a PDF (ReportLab) — usuario pidió ambos formatos, entregado solo Excel en v1
- Login con Google (Emergent OAuth) — usuario lo pidió como 2ª opción; v1 sólo JWT email/password
- Cascada al eliminar banco (reasignar/bloquear si hay cheques o flujo vinculados)
- Cuando cambia banco_id con estado "cobrado", rebalancear saldos entre bancos antiguo y nuevo
- Brute-force lockout (5 intentos fallidos → 15 min bloqueo)

### P2 — features adicionales
- Paginación en listados
- Audit log de movimientos de saldo bancario
- Notificaciones push en tiempo real (websocket)
- Anexar archivos (comprobantes) a cheques/facturas (object storage)
- Dashboard con rangos personalizables (mes/trimestre/año)

## Next tasks
Si el usuario continúa: ofrecer PDF export + Google login como P1 inmediato.

## Endpoints principales
- `POST /api/auth/login`, `/auth/register`, `/auth/logout`, `GET /auth/me`
- `CRUD /api/bancos`, `/api/clientes`, `/api/cheques`, `/api/facturas`, `/api/flujo`
- `GET /api/retenciones`, `/api/dashboard`, `/api/alertas`
- `POST /api/alertas/enviar-email`
- `GET /api/export/{modulo}` donde módulo ∈ {cheques, cartera, retenciones, bancos, flujo}
