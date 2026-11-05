import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import Engine, insert

from app.api import stats as stats_module
from app.api.stats import month_start
from app.db import run_transaction
from app.models import Expense
from app.text import search_key
from app.users import DEFAULT_CATEGORIES, ensure_user
from tests.conftest import Api

ME = "/api/v1/users/me"
CATEGORIES = "/api/v1/categories"
EXPENSES = "/api/v1/expenses"
SUMMARY = "/api/v1/stats/summary"


def categories(api: Api, sub: str = "a") -> dict[str, dict[str, Any]]:
    response = api.client.get(CATEGORIES, headers=api.as_user(sub))
    assert response.status_code == 200
    return {c["name"]: c for c in response.json()}


def add_expense(
    api: Api,
    sub: str = "a",
    *,
    category: str = "Limpieza",
    amount: int = 1_000,
    description: str = "Compra",
    spent_at: str = "2026-11-10",
) -> dict[str, Any]:
    response = api.client.post(
        EXPENSES,
        headers=api.as_user(sub),
        json={
            "category_id": categories(api, sub)[category]["id"],
            "description": description,
            "amount": amount,
            "spent_at": spent_at,
        },
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


class TestUsuario:
    def test_primera_peticion_crea_usuario_y_categorias(self, api: Api) -> None:
        response = api.client.get(ME, headers=api.as_user("nuevo"))
        assert response.status_code == 200
        assert response.json() == {
            "id": "nuevo",
            "currency": "PYG",
            "timezone": "America/Asuncion",
        }
        found = categories(api, "nuevo")
        assert set(found) == {name for name, _ in DEFAULT_CATEGORIES}
        assert [name for name, c in found.items() if c["is_fallback"]] == ["Otros"]

    def test_altas_simultaneas_crean_un_solo_usuario(self, db: Engine) -> None:
        def create(_: int) -> str:
            return run_transaction(lambda session: ensure_user(session, "simultaneo").id)

        with ThreadPoolExecutor(max_workers=8) as pool:
            assert set(pool.map(create, range(8))) == {"simultaneo"}
        with db.connect() as connection:
            total = connection.exec_driver_sql(
                "SELECT count(*) FROM categories WHERE user_id = 'simultaneo'"
            ).scalar_one()
        assert total == len(DEFAULT_CATEGORIES)

    def test_cambia_zona_horaria(self, api: Api) -> None:
        headers = api.as_user("a")
        response = api.client.patch(ME, headers=headers, json={"timezone": "America/Montevideo"})
        assert response.status_code == 200
        assert api.client.get(ME, headers=headers).json()["timezone"] == "America/Montevideo"

    @pytest.mark.parametrize("body", [{"timezone": "Marte/Base"}, {"currency": "USD"}, {"x": 1}])
    def test_rechaza_cambios_invalidos(self, api: Api, body: dict[str, str]) -> None:
        assert api.client.patch(ME, headers=api.as_user("a"), json=body).status_code == 422


class TestCategorias:
    def test_crea_renombra_y_cambia_color(self, api: Api) -> None:
        headers = api.as_user("a")
        created = api.client.post(CATEGORIES, headers=headers, json={"name": "  Mascotas "})
        assert created.status_code == 201
        assert created.json()["name"] == "Mascotas"
        url = f"{CATEGORIES}/{created.json()['id']}"
        patched = api.client.patch(url, headers=headers, json={"name": "Perro", "color": "#112233"})
        assert patched.json()["name"] == "Perro"
        assert patched.json()["color"] == "#112233"

    def test_nombre_repetido_responde_409(self, api: Api) -> None:
        body = {"name": "Limpieza"}
        response = api.client.post(CATEGORIES, headers=api.as_user("a"), json=body)
        assert response.status_code == 409

    def test_renombrar_a_uno_existente_responde_409(self, api: Api) -> None:
        url = f"{CATEGORIES}/{categories(api)['Limpieza']['id']}"
        response = api.client.patch(url, headers=api.as_user("a"), json={"name": "Hogar"})
        assert response.status_code == 409

    def test_orden_alfabetico_con_acentos_y_otros_al_final(self, api: Api) -> None:
        headers = api.as_user("a")
        for name in ("Ñoquis", "Óptica", "Zapatos"):
            api.client.post(CATEGORIES, headers=headers, json={"name": name})
        names = list(categories(api))
        assert names[-1] == "Otros"
        assert names.index("Almacén") < names.index("Bebidas")
        assert names.index("Ñoquis") < names.index("Zapatos")
        assert names.index("Óptica") < names.index("Zapatos")

    def test_borrar_mueve_los_gastos_a_otros(self, api: Api) -> None:
        expense = add_expense(api, category="Limpieza")
        found = categories(api)
        url = f"{CATEGORIES}/{found['Limpieza']['id']}"
        assert api.client.delete(url, headers=api.as_user("a")).status_code == 204
        assert "Limpieza" not in categories(api)
        listed = api.client.get(EXPENSES, headers=api.as_user("a")).json()["items"]
        assert listed[0]["id"] == expense["id"]
        assert listed[0]["category_id"] == found["Otros"]["id"]

    def test_borrar_mueve_mas_gastos_que_el_limite_de_dsql(self, api: Api, db: Engine) -> None:
        found = categories(api)
        rows = [
            {
                "id": uuid.uuid4(),
                "user_id": "a",
                "category_id": uuid.UUID(found["Limpieza"]["id"]),
                "description": "x",
                "search_key": "x",
                "amount": 1,
                "spent_at": date(2026, 1, 1),
            }
            for _ in range(3_100)
        ]
        with db.begin() as connection:
            connection.execute(insert(Expense), rows)

        url = f"{CATEGORIES}/{found['Limpieza']['id']}"
        assert api.client.delete(url, headers=api.as_user("a")).status_code == 204
        query = {"category_id": found["Otros"]["id"], "page_size": 1}
        moved = api.client.get(EXPENSES, headers=api.as_user("a"), params=query).json()
        assert moved["total"] == 3_100

    def test_otros_no_se_borra(self, api: Api) -> None:
        url = f"{CATEGORIES}/{categories(api)['Otros']['id']}"
        assert api.client.delete(url, headers=api.as_user("a")).status_code == 409
        assert "Otros" in categories(api)


class TestGastos:
    def test_crea_edita_y_borra(self, api: Api) -> None:
        headers = api.as_user("a")
        expense = add_expense(api, amount=189_400, description="Súper")
        assert expense["amount"] == 189_400
        url = f"{EXPENSES}/{expense['id']}"
        patched = api.client.patch(url, headers=headers, json={"amount": 200_000, "notes": "ok"})
        assert patched.json()["amount"] == 200_000
        assert patched.json()["notes"] == "ok"
        assert patched.json()["description"] == "Súper"
        assert api.client.delete(url, headers=headers).status_code == 204
        assert api.client.get(EXPENSES, headers=headers).json()["total"] == 0

    @pytest.mark.parametrize("amount", [0, -5, 10.5, "1000", None, 10**16])
    def test_monto_debe_ser_entero_positivo(self, api: Api, amount: Any) -> None:
        body = {
            "category_id": categories(api)["Hogar"]["id"],
            "description": "x",
            "amount": amount,
            "spent_at": "2026-11-01",
        }
        response = api.client.post(EXPENSES, headers=api.as_user("a"), json=body)
        assert response.status_code == 422

    def test_monto_grande_no_pierde_precision(self, api: Api) -> None:
        amount = 900_719_925_474_099
        assert add_expense(api, amount=amount)["amount"] == amount

    def test_filtra_por_fecha_y_categoria(self, api: Api) -> None:
        add_expense(api, category="Limpieza", spent_at="2026-10-31")
        wanted = add_expense(api, category="Limpieza", spent_at="2026-11-01")
        add_expense(api, category="Hogar", spent_at="2026-11-01")
        params = {
            "from": "2026-11-01",
            "to": "2026-11-30",
            "category_id": categories(api)["Limpieza"]["id"],
        }
        page = api.client.get(EXPENSES, headers=api.as_user("a"), params=params).json()
        assert [e["id"] for e in page["items"]] == [wanted["id"]]

    @pytest.mark.parametrize("q", ["ñandu", "ÑANDÚ", "nanduti"])
    def test_busqueda_ignora_acentos_y_mayusculas(self, api: Api, q: str) -> None:
        add_expense(api, description="Encaje Ñandutí")
        add_expense(api, description="Otra cosa")
        page = api.client.get(EXPENSES, headers=api.as_user("a"), params={"q": q}).json()
        assert [e["description"] for e in page["items"]] == ["Encaje Ñandutí"]

    def test_editar_descripcion_actualiza_la_busqueda(self, api: Api) -> None:
        expense = add_expense(api, description="Viejo")
        headers = api.as_user("a")
        url = f"{EXPENSES}/{expense['id']}"
        api.client.patch(url, headers=headers, json={"description": "Café"})
        found = api.client.get(EXPENSES, headers=headers, params={"q": "cafe"}).json()
        assert found["total"] == 1
        assert api.client.get(EXPENSES, headers=headers, params={"q": "viejo"}).json()["total"] == 0

    def test_comodines_de_busqueda_son_literales(self, api: Api) -> None:
        add_expense(api, description="Descuento")
        add_expense(api, description="Descuento 10%")
        page = api.client.get(EXPENSES, headers=api.as_user("a"), params={"q": "%"}).json()
        assert [e["description"] for e in page["items"]] == ["Descuento 10%"]

    def test_paginacion(self, api: Api) -> None:
        for day in range(1, 6):
            add_expense(api, spent_at=f"2026-11-0{day}")
        headers = api.as_user("a")
        params = {"page": 2, "page_size": 2}
        page = api.client.get(EXPENSES, headers=headers, params=params).json()
        assert page["total"] == 5
        assert [e["spent_at"] for e in page["items"]] == ["2026-11-03", "2026-11-02"]


class TestAislamiento:
    """Nadie ve ni toca datos de otro usuario."""

    def test_no_lista_gastos_ajenos(self, api: Api) -> None:
        add_expense(api, "a")
        assert api.client.get(EXPENSES, headers=api.as_user("b")).json()["total"] == 0

    @pytest.mark.parametrize("method", ["patch", "delete"])
    def test_no_toca_gastos_ajenos(self, api: Api, method: str) -> None:
        expense = add_expense(api, "a")
        url = f"{EXPENSES}/{expense['id']}"
        kwargs: dict[str, Any] = {"json": {"amount": 1}} if method == "patch" else {}
        response = getattr(api.client, method)(url, headers=api.as_user("b"), **kwargs)
        assert response.status_code == 404
        assert api.client.get(EXPENSES, headers=api.as_user("a")).json()["items"][0] == expense

    @pytest.mark.parametrize("method", ["patch", "delete"])
    def test_no_toca_categorias_ajenas(self, api: Api, method: str) -> None:
        url = f"{CATEGORIES}/{categories(api, 'a')['Limpieza']['id']}"
        categories(api, "b")
        kwargs: dict[str, Any] = {"json": {"name": "Robada"}} if method == "patch" else {}
        response = getattr(api.client, method)(url, headers=api.as_user("b"), **kwargs)
        assert response.status_code == 404
        assert "Limpieza" in categories(api, "a")

    def test_no_usa_categoria_ajena_al_crear(self, api: Api) -> None:
        foreign = categories(api, "a")["Hogar"]["id"]
        body = {"category_id": foreign, "description": "x", "amount": 1, "spent_at": "2026-11-01"}
        response = api.client.post(EXPENSES, headers=api.as_user("b"), json=body)
        assert response.status_code == 404

    def test_no_usa_categoria_ajena_al_editar(self, api: Api) -> None:
        foreign = categories(api, "a")["Hogar"]["id"]
        expense = add_expense(api, "b")
        url = f"{EXPENSES}/{expense['id']}"
        response = api.client.patch(url, headers=api.as_user("b"), json={"category_id": foreign})
        assert response.status_code == 404

    def test_estadisticas_solo_del_usuario(self, api: Api) -> None:
        add_expense(api, "a", amount=500)
        params = {"from": "2026-11-01", "to": "2026-11-30"}
        body = api.client.get(SUMMARY, headers=api.as_user("b"), params=params).json()
        assert body["total"] == 0
        assert body["by_category"] == []


class TestEstadisticas:
    def test_totales_por_categoria_y_mes(self, api: Api) -> None:
        add_expense(api, category="Limpieza", amount=1_000, spent_at="2026-11-10")
        add_expense(api, category="Limpieza", amount=2_000, spent_at="2026-11-30")
        add_expense(api, category="Hogar", amount=500, spent_at="2026-11-01")
        add_expense(api, category="Hogar", amount=7_000, spent_at="2026-10-31")
        add_expense(api, category="Hogar", amount=9_000, spent_at="2026-05-31")
        params = {"from": "2026-11-01", "to": "2026-11-30"}
        body = api.client.get(SUMMARY, headers=api.as_user("a"), params=params).json()

        assert body["total"] == 3_500
        assert [(c["name"], c["total"]) for c in body["by_category"]] == [
            ("Limpieza", 3_000),
            ("Hogar", 500),
        ]
        assert body["by_month"] == [
            {"month": "2026-06", "total": 0},
            {"month": "2026-07", "total": 0},
            {"month": "2026-08", "total": 0},
            {"month": "2026-09", "total": 0},
            {"month": "2026-10", "total": 7_000},
            {"month": "2026-11", "total": 3_500},
        ]

    def test_mes_actual_se_calcula_en_la_zona_del_usuario(
        self, api: Api, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Frozen(datetime):
            @classmethod
            def now(cls, tz: Any = None) -> Frozen:
                # 1 de diciembre en UTC, todavía 30 de noviembre en Asunción.
                moment = datetime(2026, 12, 1, 2, 0, tzinfo=UTC).astimezone(tz)
                return cls(moment.year, moment.month, moment.day, tzinfo=tz)

        monkeypatch.setattr(stats_module, "datetime", Frozen)
        add_expense(api, amount=100, spent_at="2026-11-30")
        body = api.client.get(SUMMARY, headers=api.as_user("a")).json()
        assert body["date_from"] == "2026-11-01"
        assert body["date_to"] == "2026-11-30"
        assert body["total"] == 100

    def test_rango_invertido_responde_422(self, api: Api) -> None:
        params = {"from": "2026-12-01", "to": "2026-11-01"}
        response = api.client.get(SUMMARY, headers=api.as_user("a"), params=params)
        assert response.status_code == 422

    @pytest.mark.parametrize(
        ("day", "back", "expected"),
        [
            (date(2026, 3, 15), 0, date(2026, 3, 1)),
            (date(2026, 3, 15), 5, date(2025, 10, 1)),
            (date(2026, 12, 31), -1, date(2027, 1, 1)),
        ],
    )
    def test_inicio_de_mes(self, day: date, back: int, expected: date) -> None:
        assert month_start(day, months_back=back) == expected


def test_search_key_coincide_con_la_columna(api: Api, db: Engine) -> None:
    add_expense(api, description="Ñoquis")
    with db.connect() as connection:
        stored = connection.exec_driver_sql("SELECT search_key FROM expenses").scalar_one()
    assert stored == search_key("Ñoquis")
