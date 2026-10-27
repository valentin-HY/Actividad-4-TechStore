"""API REST de TechStore (FastAPI). Todo en memoria.

Los endpoints NO validan reglas de negocio: solo llaman al metodo del dominio.
Las excepciones del dominio se traducen a codigos HTTP en los 'exception_handler'.
Ejecutar desde la raiz del proyecto:  uvicorn app.api:app --reload
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.domain import InvalidOrderData, InvalidOrderTransition, Order
from app.specifications import discount_percentage, final_total
from cargar_csv import load_fixture   # reutilizamos el cargador (no se modifica)

app = FastAPI(title="TechStore U4")

# "Repositorio" en memoria: pedido_id -> Order. No persiste entre ejecuciones.
ORDERS: dict[str, Order] = {}


def reset_repository() -> None:
    """Vuelve a cargar los 16 pedidos en DRAFT (lo usan los tests)."""
    ORDERS.clear()
    ORDERS.update(load_fixture())


reset_repository()


# ---------------------------------------------------------------- Cuerpos de peticion
class ShipRequest(BaseModel):
    tracking: str          # la regla "guia no vacia" la valida el DOMINIO, no la API


class CancelRequest(BaseModel):
    reason: str            # idem: el dominio valida que no este vacio


# ---------------------------------------------------------------- Traduccion de errores
@app.exception_handler(InvalidOrderTransition)
async def transicion_invalida(request, exc: InvalidOrderTransition):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidOrderData)
async def dato_invalido(request, exc: InvalidOrderData):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ---------------------------------------------------------------- Ayudantes
def get_order_or_404(order_id: str) -> Order:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} no existe")
    return order


def order_to_dict(order: Order) -> dict:
    # Los importes salen como TEXTO: si fueran Decimal, FastAPI los convertiria a float.
    return {
        "id": order.id,
        "customer_id": order.customer.id,
        "status": order.status.value,
        "units": order.units,
        "total": str(order.total.amount),
        "discount_percentage": discount_percentage(order),
        "final_total": str(final_total(order).amount),
        "tracking": order.tracking,
        "cancel_reason": order.cancel_reason,
        "events": [e.name for e in order.events],
    }


# ---------------------------------------------------------------- Endpoints
@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return order_to_dict(get_order_or_404(order_id))


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str):
    order = get_order_or_404(order_id)
    order.confirm()                      # si falla, el handler responde 409/422
    return order_to_dict(order)


@app.post("/orders/{order_id}/ship")
def ship_order(order_id: str, body: ShipRequest):
    order = get_order_or_404(order_id)
    order.ship(body.tracking)
    return order_to_dict(order)


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, body: CancelRequest):
    order = get_order_or_404(order_id)
    order.cancel(body.reason)
    return order_to_dict(order)
