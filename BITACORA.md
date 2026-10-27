# Bitácora E01–E15 · TechStore U4

Resultados reales obtenidos con `python ejecutar\\\_escenarios.py` (15 de 15 coinciden con lo esperado).

|Caso|Estado inicial|Operación|Resultado real|Evento emitido|Explicación|Prueba (tests/)|
|-|-|-|-|-|-|-|
|E01 (O001)|DRAFT|evaluar descuento|10% → total 2100.00 → final 1890.00|Ninguno (es una consulta)|Cumple la regla del 10%: cliente VIP, total > 500, 4 unidades (≥ 4) y sin promoción.|`test\\\_descuento\\\_vip\\\_10\\\_por\\\_ciento`|
|E02 (O002)|DRAFT|evaluar descuento|0% → total 1050.00 → final 1050.00|Ninguno (es una consulta)|No cumple el 10% (solo 2 unidades, se exigen ≥ 4) ni el 5% (total no supera 5000).|`test\\\_vip\\\_necesita\\\_4\\\_unidades`|
|E03 (O003)|DRAFT|confirmar|RECHAZO: InvalidOrderData (estado DRAFT)|Ninguno (falló `confirmar`)|El pedido tiene artículos (4 unidades), así que la precondición que falla es el cliente activo. `confirm()` valida antes de cambiar el estado: sigue en DRAFT.|`test\\\_confirmar\\\_cliente\\\_inactivo\\\_rechazado; test\\\_confirm\\\_cliente\\\_inactivo\\\_422`|
|E04 (O005)|DRAFT|evaluar descuento|0% → total 2100.00 → final 2100.00|Ninguno (es una consulta)|Tiene promoción activa; `\\\~ActivePromotionSpec` excluye el 10% aunque haya 4 unidades.|`test\\\_promocion\\\_activa\\\_bloquea\\\_ambos\\\_descuentos`|
|E05 (O006)|DRAFT|evaluar descuento|5% → total 18000.00 → final 17100.00|Ninguno (es una consulta)|Solo 1 unidad, así que no llega al 10%; el total supera 5000 y no hay promoción, aplica el 5%.|`test\\\_limite\\\_5000\\\_es\\\_estricto`|
|E06 (O007)|DRAFT|confirmar|RECHAZO: InvalidOrderData (estado DRAFT)|Ninguno (falló `confirmar`)|Pedido vacío (0 unidades); `confirm()` exige al menos un artículo. Estado sin cambios.|`test\\\_confirmar\\\_pedido\\\_vacio\\\_rechazado; test\\\_confirm\\\_pedido\\\_vacio\\\_422`|
|E07 (O008)|DRAFT|confirmar|OK, termina en CONFIRMED|OrderConfirmed|Valor frontera: 20 unidades es exactamente el máximo permitido. Hay artículos, cliente activo y estado DRAFT, así que la transición es válida y se registra el evento.|`test\\\_20\\\_unidades\\\_exactas\\\_permitidas`|
|E08 (O009)|DRAFT|agregar SKU003 x2|RECHAZO: OrderItemLimitExceeded (estado DRAFT)|Ninguno (falló `agregar SKU003 x2`)|Ya hay 19 unidades; 19 + 2 = 21 supera el límite de 20. `add\\\_item()` falla antes de modificar `items`.|`test\\\_21\\\_unidades\\\_rechazadas\\\_y\\\_pedido\\\_intacto`|
|E09 (O010)|DRAFT|evaluar descuento|0% → total 500.00 → final 500.00|Ninguno (es una consulta)|Valor frontera: el total es exactamente 500 y `MinimumAmountSpec` usa `>`, no `>=`. No hay descuento.|`test\\\_limite\\\_500\\\_es\\\_estricto`|
|E10 (O011)|DRAFT|evaluar descuento|0% → total 1500.00 → final 1500.00|Ninguno (es una consulta)|Solo 3 unidades (se exigen ≥ 4 para el 10%) y el total no supera 5000 para el 5%.|`test\\\_vip\\\_necesita\\\_4\\\_unidades`|
|E11 (O012)|DRAFT|confirmar → enviar sin guía|RECHAZO en `enviar sin guía`: InvalidOrderData (estado CONFIRMED)|OrderConfirmed; ninguno en `ship`|`confirm()` es válido y emite su evento. `ship()` exige guía no vacía; sin ella falla, el pedido sigue en CONFIRMED y no se emite OrderShipped.|`test\\\_enviar\\\_sin\\\_guia\\\_rechazado; test\\\_ship\\\_guia\\\_vacia\\\_422`|
|E12 (O013)|DRAFT|confirmar → confirmar (2.ª vez)|RECHAZO en la 2.ª vez: InvalidOrderTransition (estado CONFIRMED)|OrderConfirmed (solo uno); ninguno en la 2.ª|`confirm()` solo se permite desde DRAFT. La segunda llamada lanza la excepción y no agrega un segundo evento.|`test\\\_confirmacion\\\_doble\\\_rechazada; test\\\_confirm\\\_dos\\\_veces\\\_409`|
|E13 (O014)|DRAFT|confirmar → enviar → cancelar|RECHAZO en `cancelar`: InvalidOrderTransition (estado SHIPPED)|OrderConfirmed, OrderShipped; ninguno en `cancel`|`cancel()` exige estado CONFIRMED; un pedido ya enviado no se puede cancelar. Sigue en SHIPPED.|`test\\\_cancelar\\\_desde\\\_shipped\\\_rechazado; test\\\_cancel\\\_desde\\\_shipped\\\_409`|
|E14 (O015)|DRAFT|confirmar → enviar → devolver|OK, termina en RETURNED|OrderConfirmed, OrderShipped, OrderReturned|Cadena válida: `return\\\_order()` exige SHIPPED, y cada transición registra su evento después de cambiar el estado.|`test\\\_flujo\\\_entrega\\\_y\\\_devolucion`|
|E15 (O016)|DRAFT|confirmar → enviar → entregar|OK, termina en DELIVERED|OrderConfirmed, OrderShipped, OrderDelivered|Cadena válida: `deliver()` exige SHIPPED y registra OrderDelivered.|`test\\\_flujo\\\_entrega\\\_y\\\_devolucion`|



