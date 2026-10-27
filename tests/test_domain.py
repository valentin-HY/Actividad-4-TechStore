"""Pruebas del dominio TechStore (sin API). Ejecutar:  python -m pytest -q"""
from dataclasses import FrozenInstanceError
from datetime import timezone
from decimal import Decimal

import pytest

from app.domain import (Customer, InvalidOrderData, InvalidOrderTransition, Money, Order,
                        OrderItem, OrderItemLimitExceeded, OrderStatus)
from app.specifications import (ActivePromotionSpec, VIPCustomerSpec, discount_percentage,
                                final_total)
from cargar_csv import load_fixture


# ---------------------------------------------------------------- ayudante
def crear_pedido(vip=False, activo=True, promo=False, items=()):
    """Arma un pedido DRAFT. items = [(sku, cantidad, "precio"), ...]"""
    pedido = Order(Customer("C-TEST", vip, activo), "T-1", promo)
    for sku, cantidad, precio in items:
        pedido.add_item(OrderItem(sku, cantidad, Money(Decimal(precio))))
    return pedido


def pedido_confirmado():
    pedido = crear_pedido(items=[("SKU001", 1, "600.00")])
    pedido.confirm()
    return pedido


# ---------------------------------------------------------------- Money
def test_money_negativo_rechazado():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("-0.01"))


def test_money_float_rechazado():
    with pytest.raises(InvalidOrderData):
        Money(0.1)


def test_money_no_finito_rechazado():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("NaN"))
    with pytest.raises(InvalidOrderData):
        Money(Decimal("Infinity"))


def test_money_add_rechaza_monedas_distintas():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("1")).add(Money(Decimal("1"), "USD"))


def test_money_add_devuelve_objeto_nuevo_e_inmutable():
    a, b = Money(Decimal("10.50")), Money(Decimal("2.25"))
    c = a.add(b)
    assert c.amount == Decimal("12.75")
    assert a.amount == Decimal("10.50")      # a no cambio
    with pytest.raises(FrozenInstanceError):
        a.amount = Decimal("99")


# ---------------------------------------------------------------- OrderItem
def test_item_rechaza_sku_vacio_y_cantidad_invalida():
    with pytest.raises(InvalidOrderData):
        OrderItem("", 1, Money(Decimal("1")))
    with pytest.raises(InvalidOrderData):
        OrderItem("SKU001", 0, Money(Decimal("1")))


def test_item_subtotal_es_precio_por_cantidad():
    assert OrderItem("SKU001", 3, Money(Decimal("600.00"))).subtotal.amount == Decimal("1800.00")


# ---------------------------------------------------------------- limite de 20 unidades
def test_20_unidades_exactas_permitidas():
    pedido = crear_pedido(items=[("SKU003", 20, "120.00")])
    assert pedido.units == 20


def test_21_unidades_rechazadas_y_pedido_intacto():
    pedido = crear_pedido(items=[("SKU003", 19, "120.00")])
    with pytest.raises(OrderItemLimitExceeded):
        pedido.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))
    assert pedido.units == 19               # falla ANTES de modificar items
    assert len(pedido.items) == 1


def test_limite_cuenta_unidades_no_renglones():
    # 4 renglones x 5 unidades = 20 unidades: permitido (el limite NO es de renglones)
    pedido = crear_pedido(items=[("A", 5, "1.00"), ("B", 5, "1.00"), ("C", 5, "1.00"), ("D", 5, "1.00")])
    assert len(pedido.items) == 4 and pedido.units == 20
    with pytest.raises(OrderItemLimitExceeded):   # el renglon 5 (1 unidad) ya excede
        pedido.add_item(OrderItem("E", 1, Money(Decimal("1.00"))))


def test_add_item_fuera_de_draft_rechazado():
    pedido = pedido_confirmado()
    with pytest.raises(InvalidOrderTransition):
        pedido.add_item(OrderItem("SKU002", 1, Money(Decimal("450.00"))))


# ---------------------------------------------------------------- confirmar
def test_confirmar_cliente_inactivo_rechazado():
    pedido = crear_pedido(vip=True, activo=False, items=[("SKU001", 1, "600.00")])
    with pytest.raises(InvalidOrderData):
        pedido.confirm()
    assert pedido.status == OrderStatus.DRAFT and pedido.events == ()


def test_confirmar_pedido_vacio_rechazado():
    pedido = crear_pedido()
    with pytest.raises(InvalidOrderData):
        pedido.confirm()
    assert pedido.status == OrderStatus.DRAFT and pedido.events == ()


def test_confirmacion_doble_rechazada():
    pedido = pedido_confirmado()
    with pytest.raises(InvalidOrderTransition):
        pedido.confirm()
    assert pedido.status == OrderStatus.CONFIRMED
    assert len(pedido.events) == 1           # no se agrego un segundo evento


def test_confirmar_registra_evento_con_hora_utc():
    pedido = pedido_confirmado()
    evento = pedido.events[0]
    assert evento.name == "OrderConfirmed" and evento.order_id == "T-1"
    assert evento.occurred_at.tzinfo == timezone.utc


# ---------------------------------------------------------------- enviar / cancelar / entregar / devolver
def test_enviar_sin_guia_rechazado():
    pedido = pedido_confirmado()
    for guia in ("", "   "):
        with pytest.raises(InvalidOrderData):
            pedido.ship(guia)
    assert pedido.status == OrderStatus.CONFIRMED and len(pedido.events) == 1


def test_cancelar_desde_shipped_rechazado():
    pedido = pedido_confirmado()
    pedido.ship("GUIA-1")
    with pytest.raises(InvalidOrderTransition):
        pedido.cancel("tarde")
    assert pedido.status == OrderStatus.SHIPPED and len(pedido.events) == 2


def test_cancelar_sin_motivo_rechazado_y_con_motivo_ok():
    pedido = pedido_confirmado()
    with pytest.raises(InvalidOrderData):
        pedido.cancel("")
    pedido.cancel("Ya no lo quiere")
    assert pedido.status == OrderStatus.CANCELLED
    assert pedido.events[-1].name == "OrderCancelled"


def test_flujo_entrega_y_devolucion():
    entregado = pedido_confirmado()
    entregado.ship("G1")
    entregado.deliver()
    assert entregado.status == OrderStatus.DELIVERED
    assert [e.name for e in entregado.events] == ["OrderConfirmed", "OrderShipped", "OrderDelivered"]

    devuelto = pedido_confirmado()
    devuelto.ship("G2")
    devuelto.return_order()
    assert devuelto.status == OrderStatus.RETURNED
    assert devuelto.events[-1].name == "OrderReturned"


def test_operacion_invalida_no_agrega_eventos():
    pedido = pedido_confirmado()
    with pytest.raises(InvalidOrderTransition):
        pedido.deliver()                     # CONFIRMED -> DELIVERED no existe
    with pytest.raises(InvalidOrderTransition):
        pedido.return_order()
    assert pedido.status == OrderStatus.CONFIRMED and len(pedido.events) == 1


# ---------------------------------------------------------------- descuentos
def test_descuento_vip_10_por_ciento():
    pedido = crear_pedido(vip=True, items=[("SKU001", 2, "600.00"), ("SKU002", 2, "450.00")])
    assert pedido.total.amount == Decimal("2100.00") and pedido.units == 4
    assert discount_percentage(pedido) == 10
    assert final_total(pedido).amount == Decimal("1890.00")


def test_promocion_activa_bloquea_ambos_descuentos():
    vip_con_promo = crear_pedido(vip=True, promo=True, items=[("A", 4, "525.00")])
    caro_con_promo = crear_pedido(promo=True, items=[("B", 1, "18000.00")])
    assert discount_percentage(vip_con_promo) == 0
    assert discount_percentage(caro_con_promo) == 0


def test_limite_500_es_estricto():
    exacto = crear_pedido(vip=True, items=[("A", 4, "125.00")])        # total 500.00
    arriba = crear_pedido(vip=True, items=[("A", 4, "125.01")])        # total 500.04
    assert discount_percentage(exacto) == 0
    assert discount_percentage(arriba) == 10


def test_limite_5000_es_estricto():
    exacto = crear_pedido(items=[("A", 1, "5000.00")])
    arriba = crear_pedido(items=[("A", 1, "5000.01")])
    assert discount_percentage(exacto) == 0
    assert discount_percentage(arriba) == 5


def test_vip_necesita_4_unidades():
    tres = crear_pedido(vip=True, items=[("A", 3, "500.00")])          # 1500.00, 3 unidades
    cuatro = crear_pedido(vip=True, items=[("A", 4, "500.00")])
    assert discount_percentage(tres) == 0
    assert discount_percentage(cuatro) == 10


def test_si_cumple_ambos_gana_10_por_ciento():
    pedido = crear_pedido(vip=True, items=[("A", 4, "1500.00")])       # 6000.00: cumple 10% y 5%
    assert discount_percentage(pedido) == 10
    assert final_total(pedido).amount == Decimal("5400.00")


def test_composicion_de_specifications():
    pedido = crear_pedido(vip=True, promo=False)
    assert (VIPCustomerSpec() | ActivePromotionSpec()).is_satisfied_by(pedido)
    assert not (VIPCustomerSpec() & ActivePromotionSpec()).is_satisfied_by(pedido)
    assert (~ActivePromotionSpec()).is_satisfied_by(pedido)


# ---------------------------------------------------------------- datos de los CSV
def test_fixture_csv_totales_y_unidades():
    esperado = {"O001": ("2100.00", 4), "O002": ("1050.00", 2), "O003": ("2100.00", 4),
                "O004": ("850.00", 1), "O005": ("2100.00", 4), "O006": ("18000.00", 1),
                "O007": ("0", 0), "O008": ("2400.00", 20), "O009": ("2280.00", 19),
                "O010": ("500.00", 2), "O011": ("1500.00", 3), "O012": ("850.00", 1),
                "O013": ("600.00", 1), "O014": ("600.00", 1), "O015": ("450.00", 1),
                "O016": ("2100.00", 1)}
    pedidos = load_fixture()
    assert len(pedidos) == 16
    for pedido_id, (total, unidades) in esperado.items():
        assert str(pedidos[pedido_id].total.amount) == total, pedido_id
        assert pedidos[pedido_id].units == unidades, pedido_id
        assert pedidos[pedido_id].status == OrderStatus.DRAFT, pedido_id
