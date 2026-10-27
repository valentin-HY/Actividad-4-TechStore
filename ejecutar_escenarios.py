from decimal import Decimal

from cargar_csv import load_fixture, rows
from app.domain import DomainException, Money, OrderItem
from app.specifications import discount_percentage, final_total

PRECIOS = {x["sku"]: Decimal(x["precio_mxn"]) for x in rows("productos.csv")}

CONFIRMAR = ("confirmar", lambda o: o.confirm())
PASOS = {
    "E03": [CONFIRMAR],
    "E06": [CONFIRMAR],
    "E07": [CONFIRMAR],
    "E08": [("agregar SKU003 x2",
             lambda o: o.add_item(OrderItem("SKU003", 2, Money(PRECIOS["SKU003"]))))],
    "E11": [CONFIRMAR, ("enviar sin guia", lambda o: o.ship(""))],
    "E12": [CONFIRMAR, ("confirmar (2a vez)", lambda o: o.confirm())],
    "E13": [CONFIRMAR, ("enviar", lambda o: o.ship("GUIA-O014")),
            ("cancelar", lambda o: o.cancel("El cliente ya no lo quiere"))],
    "E14": [CONFIRMAR, ("enviar", lambda o: o.ship("GUIA-O015")),
            ("devolver", lambda o: o.return_order())],
    "E15": [CONFIRMAR, ("enviar", lambda o: o.ship("GUIA-O016")),
            ("entregar", lambda o: o.deliver())],
}

ESTADO_FINAL = {"E07": "CONFIRMED", "E14": "RETURNED", "E15": "DELIVERED"}

PASO_RECHAZO = {"rechazo": 0, "rechazo envio": 1, "rechazo segunda": 1, "rechazo cancelacion": 2}


def snapshot(order):
    """Foto del pedido para comprobar que un fallo NO cambio nada."""
    return (order.status, len(order.events), order.units, len(order.items))


def correr_pasos(order, pasos):
    """Devuelve (indice_del_fallo, nombre, excepcion, pedido_intacto) o None si todo salio bien."""
    for i, (nombre, accion) in enumerate(pasos):
        antes = snapshot(order)
        try:
            accion(order)
        except DomainException as e:
            return i, nombre, e, snapshot(order) == antes
    return None


def ejecutar(esc):
    order = load_fixture()[esc["pedido_id"]]        
    inicial = order.status.value
    caso, objetivo = esc["caso_id"], esc["objetivo"]

    # --- Escenarios de descuento
    if esc["accion"] == "evaluar_descuento":
        pct = discount_percentage(order)
        resultado = f"{pct}% -> total {order.total.amount} -> final {final_total(order).amount}"
        return inicial, "evaluar descuento", resultado, "sin evento: es una consulta", \
            pct == int(objetivo.rstrip("%")), objetivo

    pasos = PASOS[caso]
    falla = correr_pasos(order, pasos)
    eventos = [e.name for e in order.events]

    if falla is None:
        resultado = f"OK, termina en {order.status.value}"
        evento = ", ".join(eventos)
        ok = objetivo == "exito" and order.status.value == ESTADO_FINAL[caso]
    else:
        i, nombre, exc, intacto = falla
        resultado = f"RECHAZO en '{nombre}': {type(exc).__name__} (estado {order.status.value})"
        evento = (", ".join(eventos) + "; " if eventos else "") + f"sin evento: falló '{nombre}'"
        ok = (objetivo in PASO_RECHAZO and i == PASO_RECHAZO[objetivo] and intacto)
    operacion = " -> ".join(n for n, _ in pasos)
    return inicial, operacion, resultado, evento, ok, objetivo


def main():
    print("| Caso | Estado inicial | Operación | Resultado real | Evento emitido | ¿Coincide? (esperado) |")
    print("|---|---|---|---|---|---|")
    total_ok = 0
    escenarios = rows("escenarios.csv")
    for esc in escenarios:
        inicial, operacion, resultado, evento, ok, objetivo = ejecutar(esc)
        total_ok += ok
        print(f"| {esc['caso_id']} ({esc['pedido_id']}) | {inicial} | {operacion} | {resultado} "
              f"| {evento} | {'Sí' if ok else 'NO'} ({objetivo}) |")
    print(f"\nCoinciden {total_ok} de {len(escenarios)} escenarios.")


if __name__ == "__main__":
    main()
