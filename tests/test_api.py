"""Pruebas de la API con TestClient (no hace falta levantar uvicorn)."""
import pytest
from fastapi.testclient import TestClient

from app.api import app, reset_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def pedidos_recien_cargados():
    """Antes de CADA prueba se recargan los 16 pedidos en DRAFT."""
    reset_repository()


def test_get_pedido_existente_200():
    r = client.get("/orders/O001")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "DRAFT"
    assert data["units"] == 4
    assert data["total"] == "2100.00"
    assert data["discount_percentage"] == 10
    assert data["final_total"] == "1890.00"


def test_get_pedido_inexistente_404():
    assert client.get("/orders/O999").status_code == 404


def test_confirm_pedido_inexistente_404():
    assert client.post("/orders/O999/confirm").status_code == 404


def test_confirm_exitoso_200():
    r = client.post("/orders/O001/confirm")
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"
    assert r.json()["events"] == ["OrderConfirmed"]


def test_confirm_dos_veces_409():
    assert client.post("/orders/O013/confirm").status_code == 200
    r = client.post("/orders/O013/confirm")
    assert r.status_code == 409
    # el pedido no cambio: sigue CONFIRMED con un solo evento
    estado = client.get("/orders/O013").json()
    assert estado["status"] == "CONFIRMED"
    assert estado["events"] == ["OrderConfirmed"]


def test_confirm_cliente_inactivo_422():
    assert client.post("/orders/O003/confirm").status_code == 422
    assert client.get("/orders/O003").json()["status"] == "DRAFT"


def test_confirm_pedido_vacio_422():
    assert client.post("/orders/O007/confirm").status_code == 422
    assert client.get("/orders/O007").json()["status"] == "DRAFT"


def test_ship_guia_vacia_422():
    client.post("/orders/O012/confirm")
    r = client.post("/orders/O012/ship", json={"tracking": ""})
    assert r.status_code == 422
    assert client.get("/orders/O012").json()["status"] == "CONFIRMED"


def test_ship_exitoso_200():
    client.post("/orders/O014/confirm")
    r = client.post("/orders/O014/ship", json={"tracking": "GUIA-123"})
    assert r.status_code == 200
    assert r.json()["status"] == "SHIPPED"
    assert r.json()["tracking"] == "GUIA-123"


def test_cancel_motivo_vacio_422_y_luego_exitoso():
    client.post("/orders/O012/confirm")
    assert client.post("/orders/O012/cancel", json={"reason": ""}).status_code == 422
    r = client.post("/orders/O012/cancel", json={"reason": "Cliente ya no lo quiere"})
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


def test_cancel_desde_shipped_409():
    client.post("/orders/O014/confirm")
    client.post("/orders/O014/ship", json={"tracking": "GUIA-123"})
    r = client.post("/orders/O014/cancel", json={"reason": "tarde"})
    assert r.status_code == 409
    assert client.get("/orders/O014").json()["status"] == "SHIPPED"
