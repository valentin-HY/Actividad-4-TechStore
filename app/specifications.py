"""Specification Pattern: cada regla de negocio es un objeto pequeno que se puede combinar.

Se componen con operadores:  a & b  (AND),  a | b  (OR),  ~a  (NOT).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.domain import Money, Order


# ---------------------------------------------------------------- Base
class Specification:
    """Clase base: las hijas implementan is_satisfied_by(order) -> bool."""

    def is_satisfied_by(self, order: Order) -> bool:
        raise NotImplementedError

    def __and__(self, other: Specification) -> Specification:
        return AndSpec(self, other)

    def __or__(self, other: Specification) -> Specification:
        return OrSpec(self, other)

    def __invert__(self) -> Specification:
        return NotSpec(self)


# ---------------------------------------------------------------- Composicion
class AndSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left, self.right = left, right

    def is_satisfied_by(self, order: Order) -> bool:
        return self.left.is_satisfied_by(order) and self.right.is_satisfied_by(order)


class OrSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left, self.right = left, right

    def is_satisfied_by(self, order: Order) -> bool:
        return self.left.is_satisfied_by(order) or self.right.is_satisfied_by(order)


class NotSpec(Specification):
    def __init__(self, inner: Specification):
        self.inner = inner

    def is_satisfied_by(self, order: Order) -> bool:
        return not self.inner.is_satisfied_by(order)


# ---------------------------------------------------------------- Reglas simples
class MinimumAmountSpec(Specification):
    """Total ESTRICTAMENTE mayor al umbral (500 exacto NO cumple)."""

    def __init__(self, threshold: Decimal):
        self.threshold = Decimal(threshold)

    def is_satisfied_by(self, order: Order) -> bool:
        return order.total.amount > self.threshold  # '>' y no '>='


class VIPCustomerSpec(Specification):
    def is_satisfied_by(self, order: Order) -> bool:
        return order.customer.is_vip


class MinimumUnitsSpec(Specification):
    """Unidades (suma de cantidades) mayores o IGUALES al minimo."""

    def __init__(self, minimum: int = 4):
        self.minimum = minimum

    def is_satisfied_by(self, order: Order) -> bool:
        return order.units >= self.minimum  # '>=' : 4 unidades si cumple


class ActivePromotionSpec(Specification):
    def is_satisfied_by(self, order: Order) -> bool:
        return order.has_promotion


# ---------------------------------------------------------------- Reglas de descuento
# Descuento 10%: VIP AND total > 500 AND unidades >= 4 AND NOT promocion
DISCOUNT_10 = (VIPCustomerSpec()
               & MinimumAmountSpec(Decimal("500"))
               & MinimumUnitsSpec(4)
               & ~ActivePromotionSpec())

# Descuento 5%: total > 5000 AND NOT promocion
DISCOUNT_5 = MinimumAmountSpec(Decimal("5000")) & ~ActivePromotionSpec()


def discount_percentage(order: Order) -> int:
    """Devuelve 10, 5 o 0. Se evalua primero el 10% para darle prioridad."""
    if DISCOUNT_10.is_satisfied_by(order):
        return 10
    if DISCOUNT_5.is_satisfied_by(order):
        return 5
    return 0


def final_total(order: Order) -> Money:
    """Total despues del descuento, redondeado a centavos (ROUND_HALF_UP)."""
    pct = discount_percentage(order)
    factor = (Decimal(100) - Decimal(pct)) / Decimal(100)   # 10% -> 0.90
    amount = (order.total.amount * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Money(amount)
