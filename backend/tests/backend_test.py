"""Backend API tests for Sistema Integral de Control Financiero y Cartera."""
import os
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tesoreria-app-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@finanzas.com", "password": "admin123"}
FINANCIERO = {"email": "financiero@finanzas.com", "password": "financiero123"}
CONSULTA = {"email": "consulta@finanzas.com", "password": "consulta123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["email"] == creds["email"]
    assert "role" in data
    return s, data


@pytest.fixture(scope="module")
def admin_sess():
    s, _ = _login(ADMIN)
    return s


@pytest.fixture(scope="module")
def consulta_sess():
    s, _ = _login(CONSULTA)
    return s


@pytest.fixture(scope="module")
def finan_sess():
    s, _ = _login(FINANCIERO)
    return s


# ---------------- AUTH ----------------
class TestAuth:
    def test_login_admin_sets_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=ADMIN)
        assert r.status_code == 200
        assert "access_token" in s.cookies
        assert r.json()["role"] == "admin"

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": "x@y.com", "password": "bad"})
        assert r.status_code == 401

    def test_me_via_cookie(self, admin_sess):
        r = admin_sess.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]
        assert "password_hash" not in r.json()

    def test_me_via_bearer(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=ADMIN)
        token = s.cookies.get("access_token")
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    def test_logout(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=ADMIN)
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # cookie cleared
        r2 = s.get(f"{API}/auth/me")
        assert r2.status_code == 401

    def test_no_auth_returns_401(self):
        r = requests.get(f"{API}/bancos")
        assert r.status_code == 401


# ---------------- ROLES ----------------
class TestRoles:
    def test_consulta_can_read_bancos(self, consulta_sess):
        r = consulta_sess.get(f"{API}/bancos")
        assert r.status_code == 200

    def test_consulta_cannot_create_banco(self, consulta_sess):
        r = consulta_sess.post(f"{API}/bancos", json={"nombre": "X", "saldo_efectivo": 100})
        assert r.status_code == 403


# ---------------- BANCOS ----------------
class TestBancos:
    def test_list_bancos_seeded(self, admin_sess):
        r = admin_sess.get(f"{API}/bancos")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 3
        for b in items:
            expected = round(b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"], 2)
            assert b["disponible"] == expected

    def test_create_banco_admin(self, admin_sess):
        payload = {"nombre": "TEST_Banco", "saldo_efectivo": 500, "sobregiro_asignado": 100, "sobregiro_utilizado": 20}
        r = admin_sess.post(f"{API}/bancos", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["disponible"] == 580.0
        # cleanup
        admin_sess.delete(f"{API}/bancos/{data['id']}")


# ---------------- CHEQUES ----------------
class TestCheques:
    def test_list_cheques(self, admin_sess):
        r = admin_sess.get(f"{API}/cheques")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert "dias_restantes" in items[0]

    def test_filter_pendiente(self, admin_sess):
        r = admin_sess.get(f"{API}/cheques?estado=pendiente")
        assert r.status_code == 200
        assert all(c["estado"] == "pendiente" for c in r.json())

    def test_create_cobrado_decrements_bank(self, admin_sess):
        bancos = admin_sess.get(f"{API}/bancos").json()
        banco = bancos[0]
        before = banco["saldo_efectivo"]
        payload = {
            "numero": "TEST_CHK1", "valor": 123.45, "beneficiario": "Test",
            "fecha_emision": date.today().isoformat(), "fecha_cobro": date.today().isoformat(),
            "estado": "cobrado", "banco_id": banco["id"], "motivo": "t"
        }
        r = admin_sess.post(f"{API}/cheques", json=payload)
        assert r.status_code == 200
        cid = r.json()["id"]
        after = next(b for b in admin_sess.get(f"{API}/bancos").json() if b["id"] == banco["id"])["saldo_efectivo"]
        assert round(before - after, 2) == 123.45
        # cleanup: delete cheque and restore bank
        admin_sess.delete(f"{API}/cheques/{cid}")
        admin_sess.put(f"{API}/bancos/{banco['id']}", json={
            "nombre": banco["nombre"], "saldo_efectivo": before,
            "sobregiro_asignado": banco["sobregiro_asignado"],
            "sobregiro_utilizado": banco["sobregiro_utilizado"]
        })

    def test_update_transitions_to_cobrado(self, admin_sess):
        bancos = admin_sess.get(f"{API}/bancos").json()
        banco = bancos[0]
        before = banco["saldo_efectivo"]
        pay = {"numero": "TEST_CHK2", "valor": 50.0, "beneficiario": "T",
               "fecha_emision": date.today().isoformat(),
               "fecha_cobro": (date.today()+timedelta(days=5)).isoformat(),
               "estado": "pendiente", "banco_id": banco["id"]}
        cid = admin_sess.post(f"{API}/cheques", json=pay).json()["id"]
        pay["estado"] = "cobrado"
        r = admin_sess.put(f"{API}/cheques/{cid}", json=pay)
        assert r.status_code == 200
        after = next(b for b in admin_sess.get(f"{API}/bancos").json() if b["id"] == banco["id"])["saldo_efectivo"]
        assert round(before - after, 2) == 50.0
        admin_sess.delete(f"{API}/cheques/{cid}")
        admin_sess.put(f"{API}/bancos/{banco['id']}", json={
            "nombre": banco["nombre"], "saldo_efectivo": before,
            "sobregiro_asignado": banco["sobregiro_asignado"],
            "sobregiro_utilizado": banco["sobregiro_utilizado"]})


# ---------------- CARTERA ----------------
class TestFacturas:
    def test_list_facturas_total(self, admin_sess):
        r = admin_sess.get(f"{API}/facturas")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        for f in items:
            assert f["total"] == round(f["subtotal"] - f["anticipos"] - f["retencion"], 2)

    def test_create_factura(self, admin_sess):
        clientes = admin_sess.get(f"{API}/clientes").json()
        assert clientes
        payload = {"cliente_id": clientes[0]["id"], "numero_documento": "TEST_F1",
                   "fecha_emision": date.today().isoformat(), "estado": "pendiente",
                   "subtotal": 1000, "anticipos": 100, "retencion": 50}
        r = admin_sess.post(f"{API}/facturas", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 850.0
        admin_sess.delete(f"{API}/facturas/{d['id']}")


# ---------------- CLIENTES ----------------
class TestClientes:
    def test_list_clientes(self, admin_sess):
        r = admin_sess.get(f"{API}/clientes")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_create_cliente(self, admin_sess):
        r = admin_sess.post(f"{API}/clientes", json={"nombre": "TEST_Cliente", "ruc": "123", "email": "t@t.com"})
        assert r.status_code == 200
        cid = r.json()["id"]
        admin_sess.delete(f"{API}/clientes/{cid}")


# ---------------- RETENCIONES ----------------
class TestRetenciones:
    def test_retenciones_include_cliente_nombre(self, admin_sess):
        r = admin_sess.get(f"{API}/retenciones")
        assert r.status_code == 200
        for item in r.json():
            assert "cliente_nombre" in item
            assert item["valor_retenido"] > 0


# ---------------- FLUJO ----------------
class TestFlujo:
    def test_list_flujo_filters(self, admin_sess):
        r = admin_sess.get(f"{API}/flujo")
        assert r.status_code == 200
        today = date.today().isoformat()
        r2 = admin_sess.get(f"{API}/flujo?desde={today}&hasta={today}")
        assert r2.status_code == 200

    def test_create_flujo(self, admin_sess):
        r = admin_sess.post(f"{API}/flujo", json={
            "fecha": date.today().isoformat(), "tipo": "ingreso",
            "descripcion": "TEST_flujo", "monto": 100.0
        })
        assert r.status_code == 200
        admin_sess.delete(f"{API}/flujo/{r.json()['id']}")


# ---------------- DASHBOARD ----------------
class TestDashboard:
    def test_dashboard_shape(self, admin_sess):
        r = admin_sess.get(f"{API}/dashboard")
        assert r.status_code == 200
        d = r.json()
        for k in ["saldo_total_bancos", "total_cheques_pendientes", "cartera_pendiente",
                  "total_retenciones", "disponible_real"]:
            assert k in d["kpis"]
        assert len(d["flujo_7dias"]) == 7
        assert isinstance(d["cheques_por_estado"], list)
        assert isinstance(d["cartera_por_cliente"], list)
        assert isinstance(d["bancos"], list)


# ---------------- ALERTAS ----------------
class TestAlertas:
    def test_alertas_sorted(self, admin_sess):
        r = admin_sess.get(f"{API}/alertas")
        assert r.status_code == 200
        order = {"high": 0, "warning": 1, "info": 2}
        prev = -1
        for a in r.json():
            assert a["priority"] in order
            assert order[a["priority"]] >= prev
            prev = order[a["priority"]]

    def test_enviar_email_stub(self, admin_sess):
        r = admin_sess.post(f"{API}/alertas/enviar-email")
        assert r.status_code == 200
        data = r.json()
        # Stub mode: sent should be False since RESEND_API_KEY is empty
        assert data.get("sent") is False

    def test_consulta_cannot_send_email(self, consulta_sess):
        r = consulta_sess.post(f"{API}/alertas/enviar-email")
        assert r.status_code == 403


# ---------------- EXPORT ----------------
class TestExport:
    @pytest.mark.parametrize("modulo", ["cheques", "cartera", "retenciones", "bancos", "flujo"])
    def test_export_xlsx(self, admin_sess, modulo):
        r = admin_sess.get(f"{API}/export/{modulo}")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "")
        # xlsx starts with PK (zip)
        assert r.content[:2] == b"PK"

    def test_export_invalid(self, admin_sess):
        r = admin_sess.get(f"{API}/export/xxx")
        assert r.status_code == 400
