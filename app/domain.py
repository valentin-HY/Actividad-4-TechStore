"""Dominio TechStore (Actividad 4): Value Objects, entidades, excepciones y eventos.

Etapa 1: modelo de datos + add_item con limite de 20 unidades.
Etapa 3: se agregan las transiciones (confirm, ship, cancel, deliver, return_order).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum

MAX_UNITS = 20  # maximo de UNIDADES por pedido (suma de cantidades, no renglones)


# ---------------------------------------------------------------- Excepciones
class DomainException(Exception):
    """Base de todos los errores de negocio."""


class InvalidOrderData(DomainException):
    """Dato invalido (importe negativo, sku vacio, cantidad <= 0, guia vacia...)."""


class InvalidOrderTransition(DomainException):
    """Operacion no permitida desde el estado actual del pedido."""


class OrderItemLimitExceeded(DomainException):
    """El pedido pasaria de 20 unidades."""


# ---------------------------------------------------------------- Value Objects
@dataclass(frozen=True)  # frozen = inmutable
class Money:
    """Importe en MXN. Usa Decimal (float acumula errores binarios: 0.1 + 0.2 != 0.3)."""
    amount: Decimal
    currency: str = "MXN"

    def __post_init__(self):
        # Rechazamos float y bool de entrada; aceptamos Decimal, int o str.
        if isinstance(self.amount, (float, bool)):
            raise InvalidOrderData("Money no acepta float; usa Decimal")
        try:
            value = Decimal(self.amount)
        except (InvalidOperation, TypeError, ValueError):
            raise InvalidOrderData(f"Importe invalido: {self.amount!r}")
        if not value.is_finite():
            raise InvalidOrderData("El importe debe ser finito")
        if value < 0:
            raise InvalidOrderData("El importe no puede ser negativo")
        # En un dataclass frozen se asigna con object.__setattr__
        object.__setattr__(self, "amount", value)

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise InvalidOrderData("No se pueden sumar monedas distintas")
        return Money(self.amount + other.amount, self.currency)  # objeto NUEVO

    def multiply(self, factor) -> Money:
        """Precio x cantidad (int) o x factor Decimal."""
        if isinstance(factor, float):
            raise InvalidOrderData("El factor no puede ser float")
        return Money(self.amount * Decimal(factor), self.currency)


@dataclass(frozen=True)
class OrderItem:
    """Renglon del pedido: sku + cantidad + precio unitario."""
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not self.sku or not str(self.sku).strip():
            raise InvalidOrderData("El sku no puede estar vacio")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) or self.quantity <= 0:
            raise InvalidOrderData("La cantidad debe ser un entero mayor que 0")

    @property
    def subtotal(self) -> Money:
        # Calculado, nunca almacenado: asi no puede quedar desactualizado.
        return self.unit_price.multiply(self.quantity)


# ---------------------------------------------------------------- Entidad Customer
@dataclass
class Customer:
    id: str
    is_vip: bool
    active: bool


# ---------------------------------------------------------------- Estados y eventos
class OrderStatus(Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


@dataclass(frozen=True)
class DomainEvent:
    """Hecho ya ocurrido; inmutable."""
    name: str
    order_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------- Aggregate Root
class Order:
    """Raiz del agregado: todo cambio a los items/estado pasa por aqui."""

    def __init__(self, customer: Customer, id: str, has_promotion: bool = False):
        self.id = id
        self.customer = customer
        self.has_promotion = has_promotion
        self._items: list[OrderItem] = []
        self._status = OrderStatus.DRAFT
        self._events: list[DomainEvent] = []
        self.tracking: str | None = None
        self.cancel_reason: str | None = None

    # --- consultas (solo lectura)
    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def items(self) -> tuple[OrderItem, ...]:
        return tuple(self._items)  # copia: nadie modifica la lista desde fuera

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)

    @property
    def units(self) -> int:
        """Suma de CANTIDADES (no cuenta renglones)."""
        return sum(i.quantity for i in self._items)

    @property
    def total(self) -> Money:
        result = Money(Decimal("0"))
        for item in self._items:
            result = result.add(item.subtotal)
        return result

    # --- comandos
    def add_item(self, item: OrderItem) -> None:
        # 1) validar (nada se modifica si algo falla)
        if self._status is not OrderStatus.DRAFT:
            raise InvalidOrderTransition(
                f"Solo se agregan articulos en DRAFT (estado actual: {self._status.value})")
        if self.units + item.quantity > MAX_UNITS:
            raise OrderItemLimitExceeded(
                f"Maximo {MAX_UNITS} unidades: tiene {self.units} y se intentan agregar {item.quantity}")
        # 2) cambiar
        self._items.append(item)

    # ------------------------------------------------------------ transiciones (etapa 3)
    # Orden en TODAS: 1) validar  2) cambiar status  3) registrar evento.
    # Si algo falla en el paso 1 se lanza la excepcion y NO cambia nada.

    def _require_status(self, expected: OrderStatus, action: str) -> None:
        if self._status is not expected:
            raise InvalidOrderTransition(
                f"No se puede {action} desde {self._status.value} (se requiere {expected.value})")

    def _record(self, event_name: str) -> None:
        self._events.append(DomainEvent(name=event_name, order_id=self.id))

    def confirm(self) -> None:
        """DRAFT -> CONFIRMED. Requiere articulos y cliente activo."""
        self._require_status(OrderStatus.DRAFT, "confirmar")
        if not self._items:
            raise InvalidOrderData("No se puede confirmar un pedido sin articulos")
        if not self.customer.active:
            raise InvalidOrderData("No se puede confirmar: el cliente esta inactivo")
        self._status = OrderStatus.CONFIRMED
        self._record("OrderConfirmed")

    def ship(self, tracking: str) -> None:
        """CONFIRMED -> SHIPPED. Requiere guia no vacia."""
        self._require_status(OrderStatus.CONFIRMED, "enviar")
        if not tracking or not tracking.strip():
            raise InvalidOrderData("La guia de envio no puede estar vacia")
        self.tracking = tracking.strip()
        self._status = OrderStatus.SHIPPED
        self._record("OrderShipped")

    def cancel(self, reason: str) -> None:
        """CONFIRMED -> CANCELLED. Requiere motivo no vacio."""
        self._require_status(OrderStatus.CONFIRMED, "cancelar")
        if not reason or not reason.strip():
            raise InvalidOrderData("El motivo de cancelacion no puede estar vacio")
        self.cancel_reason = reason.strip()
        self._status = OrderStatus.CANCELLED
        self._record("OrderCancelled")

    def deliver(self) -> None:
        """SHIPPED -> DELIVERED."""
        self._require_status(OrderStatus.SHIPPED, "entregar")
        self._status = OrderStatus.DELIVERED
        self._record("OrderDelivered")

    def return_order(self) -> None:
        """SHIPPED -> RETURNED."""
        self._require_status(OrderStatus.SHIPPED, "devolver")
        self._status = OrderStatus.RETURNED
        self._record("OrderReturned")
