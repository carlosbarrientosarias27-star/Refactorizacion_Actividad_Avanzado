"""
BLOQUE 4 — Reto de refactorización total: do_stuff()
=====================================================
Todos los tipos de refactorización aplicados + métricas + post-mortem
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Protocol
from abc import abstractmethod


# ═══════════════════════════════════════════════════════════════
# CÓDIGO ORIGINAL (referencia)
# ═══════════════════════════════════════════════════════════════
"""
def do_stuff(ords, disc, inv):
    res = []
    for o in ords:
        t = 0
        for item in o['items']:
            found = False
            for i in inv:
                if i['id'] == item['id']:
                    if i['stock'] > 0:
                        t += item['qty'] * i['price']
                        found = True
                        break
            if not found:
                print('Item not found: ' + str(item['id']))
        if o['type'] == 'premium':
            t = t * (1 - disc['premium'])
        elif o['type'] == 'vip':
            t = t * (1 - disc['vip'])
        if t > 1000:
            t = t * 0.95
        elif o['type'] == 'bulk':
            if len(o['items']) > 10:
                t = t * (1 - disc['bulk'])
        res.append({'order_id': o['id'], 'total': round(t, 2)})
    return res
"""

# ═══════════════════════════════════════════════════════════════
# EJERCICIO 4.1 — PLAN DE REFACTORIZACIÓN (escrito ANTES de la IA)
# ═══════════════════════════════════════════════════════════════
"""
┌────┬──────────────────────────────────────┬──────────────────────────┬───────────────────────────────────────┐
│ Nº │ Qué cambiaría                        │ Tipo de refactorización  │ Por qué tiene prioridad               │
├────┼──────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────┤
│ 1  │ Nombres: do_stuff→process_orders,    │ Mejora de nomenclatura   │ Sin nombres no se puede razonar       │
│    │ ords→orders, disc→discounts,         │                          │ sobre el código. Es el primer paso.   │
│    │ inv→inventory, t→total, o→order      │                          │                                       │
├────┼──────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────┤
│ 2  │ O(n·m·k) → O(n·m): pre-indexar      │ Optimización             │ El bucle triple es el mayor           │
│    │ inventario en dict {id: item}        │                          │ problema de rendimiento.              │
│    │ antes del bucle principal            │                          │                                       │
├────┼──────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────┤
│ 3  │ Crear dataclasses: Order, OrderItem, │ Modularización (SRP)     │ Los dicts sin tipo son frágiles       │
│    │ InventoryItem, OrderResult           │ + Modernización          │ y sin autocompletado.                 │
├────┼──────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────┤
│ 4  │ Extraer lógica de descuentos a       │ Patrón de diseño         │ Añadir nuevo tipo de cliente ahora    │
│    │ Strategy pattern (DiscountStrategy)  │ (Strategy)               │ requiere modificar do_stuff.          │
│    │                                      │                          │ Con Strategy, solo añadir clase.      │
├────┼──────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────┤
│ 5  │ Simplificar condicionales anidados   │ Simplificación de        │ El elif o['type']=='bulk' dentro      │
│    │ (bug: bulk descuento está en         │ condicionales            │ del elif t>1000 nunca se ejecuta      │
│    │ rama elif de t>1000, nunca se aplica)│                          │ → hay un BUG de lógica.               │
├────┼──────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────┤
│ 6  │ Cambiar print() a logging +          │ Modernización            │ print() en producción no es           │
│    │ retornar lista de errores en vez     │                          │ observable. logging permite           │
│    │ de imprimir silenciosamente          │                          │ niveles, ficheros, formatters.        │
└────┴──────────────────────────────────────┴──────────────────────────┴───────────────────────────────────────┘

BUG DETECTADO ANTES DE LA IA:
El elif o['type'] == 'bulk' está dentro de la rama `elif t > 1000`,
por lo que el descuento bulk NUNCA se aplica si t > 1000.
Probablemente el descuento de volumen (bulk) debería ser independiente.
"""

# ═══════════════════════════════════════════════════════════════
# PASO 1 — Modelos de datos (nomenclatura + dataclasses)
# ═══════════════════════════════════════════════════════════════
import logging

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    STANDARD = "standard"
    PREMIUM   = "premium"
    VIP       = "vip"
    BULK      = "bulk"


@dataclass(frozen=True)
class OrderItem:
    """Referencia a un producto dentro de un pedido."""
    id: int
    qty: int


@dataclass(frozen=True)
class InventoryItem:
    """Producto disponible en inventario."""
    id: int
    price: float
    stock: int

    def is_available(self) -> bool:
        return self.stock > 0


@dataclass
class Order:
    """Pedido de un cliente."""
    id: int
    type: OrderType
    items: List[OrderItem]


@dataclass(frozen=True)
class OrderResult:
    """Resultado del procesamiento de un pedido."""
    order_id: int
    total: float
    warnings: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# PASO 2 — Patrón Strategy para descuentos
# ═══════════════════════════════════════════════════════════════

class DiscountStrategy(Protocol):
    """Interfaz de estrategia de descuento."""
    @abstractmethod
    def apply(self, subtotal: float, order: Order) -> float: ...
    @property
    @abstractmethod
    def name(self) -> str: ...


@dataclass
class NoDiscount:
    """Sin descuento por tipo de cliente."""
    name: str = "sin_descuento"

    def apply(self, subtotal: float, order: Order) -> float:
        return subtotal


@dataclass
class PercentageDiscount:
    """Descuento porcentual fijo por tipo de cliente."""
    rate: float
    name: str = "descuento_porcentual"

    def apply(self, subtotal: float, order: Order) -> float:
        return subtotal * (1 - self.rate)


@dataclass
class BulkDiscount:
    """
    Descuento por volumen: solo si el pedido tiene más de min_items líneas.
    Corrige el bug original donde el bulk discount estaba dentro del elif t > 1000.
    """
    rate: float
    min_items: int = 10
    name: str = "descuento_bulk"

    def apply(self, subtotal: float, order: Order) -> float:
        if len(order.items) > self.min_items:
            return subtotal * (1 - self.rate)
        return subtotal


@dataclass
class HighValueDiscount:
    """Descuento adicional del 5% en pedidos superiores a un umbral."""
    threshold: float = 1_000.0
    rate: float = 0.05

    def apply(self, subtotal: float) -> float:
        return subtotal * (1 - self.rate) if subtotal > self.threshold else subtotal


# ═══════════════════════════════════════════════════════════════
# PASO 3 — Indexación O(k→1) del inventario
# ═══════════════════════════════════════════════════════════════

def build_inventory_index(inventory: List[InventoryItem]) -> Dict[int, InventoryItem]:
    """
    Pre-indexa el inventario en O(k) una sola vez.
    Elimina el bucle interno O(k) que se repetía por cada ítem de cada pedido.

    Complejidad: O(k) donde k = número de ítems en inventario.
    Búsquedas posteriores: O(1) en vez de O(k).
    """
    return {item.id: item for item in inventory}


# ═══════════════════════════════════════════════════════════════
# PASO 4 — Cálculo de subtotal de un pedido
# ═══════════════════════════════════════════════════════════════

def calculate_order_subtotal(
    order: Order,
    inventory_index: Dict[int, InventoryItem],
) -> tuple[float, List[str]]:
    """
    Calcula el subtotal de un pedido consultando el inventario indexado.
    Retorna (subtotal, lista_de_warnings) en vez de hacer print().

    Complejidad: O(m) donde m = líneas del pedido.
    """
    subtotal = 0.0
    warnings: List[str] = []

    for item in order.items:
        inv_item = inventory_index.get(item.id)

        if inv_item is None:
            msg = f"Ítem {item.id} no encontrado en inventario (order {order.id})"
            warnings.append(msg)
            logger.warning(msg)
            continue

        if not inv_item.is_available():
            msg = f"Ítem {item.id} sin stock (order {order.id})"
            warnings.append(msg)
            logger.warning(msg)
            continue

        subtotal += item.qty * inv_item.price

    return subtotal, warnings


# ═══════════════════════════════════════════════════════════════
# PASO 5 — Procesamiento principal (complejidad O(n·m))
# ═══════════════════════════════════════════════════════════════

def build_discount_registry(discounts: Dict[str, float]) -> Dict[OrderType, DiscountStrategy]:
    """
    Construye el registro de estrategias de descuento a partir del dict de tasas.
    Añadir un nuevo tipo de cliente = añadir una entrada aquí, sin tocar process_orders.
    """
    return {
        OrderType.STANDARD: NoDiscount(),
        OrderType.PREMIUM:  PercentageDiscount(rate=discounts.get("premium", 0.0),
                                                name="descuento_premium"),
        OrderType.VIP:      PercentageDiscount(rate=discounts.get("vip", 0.0),
                                                name="descuento_vip"),
        OrderType.BULK:     BulkDiscount(rate=discounts.get("bulk", 0.0)),
    }


def process_orders(
    orders: List[Order],
    discounts: Dict[str, float],
    inventory: List[InventoryItem],
) -> List[OrderResult]:
    """
    Procesa una lista de pedidos aplicando descuentos e inventario.

    Complejidad temporal: O(n·m) donde n=pedidos, m=líneas por pedido.
    (Antes era O(n·m·k) por el bucle triple sobre inventario.)

    Tipos de refactorización aplicados:
    - Nomenclatura: nombres descriptivos en todos los símbolos
    - Modularización: dataclasses, funciones puras con SRP
    - Optimización: inventario pre-indexado → O(1) por búsqueda
    - Patrón Strategy: descuentos extensibles sin modificar esta función
    - Simplificación: condicionales planos, sin anidamiento innecesario
    - Modernización: dataclasses, Enum, Protocol, type hints, logging

    Args:
        orders:    Lista de pedidos a procesar.
        discounts: Dict con tasas de descuento {'premium': 0.1, 'vip': 0.2, 'bulk': 0.15}.
        inventory: Lista de ítems disponibles.

    Returns:
        Lista de OrderResult con totales calculados.
    """
    # O(k) una sola vez: elimina el bucle triple del original
    inventory_index = build_inventory_index(inventory)
    discount_registry = build_discount_registry(discounts)
    high_value_discount = HighValueDiscount(threshold=1_000.0, rate=0.05)

    results: List[OrderResult] = []

    for order in orders:                                    # O(n)
        subtotal, warnings = calculate_order_subtotal(     # O(m)
            order, inventory_index
        )

        # Descuento por tipo de cliente (Strategy pattern)
        strategy = discount_registry.get(order.type, NoDiscount())
        total = strategy.apply(subtotal, order)

        # Descuento adicional por alto valor (independiente del tipo de cliente)
        # CORRECCIÓN del bug original: esto se aplica SIEMPRE que t > 1000,
        # no solo cuando type != 'bulk'
        total = high_value_discount.apply(total)

        results.append(OrderResult(
            order_id=order.id,
            total=round(total, 2),
            warnings=warnings,
        ))

    return results


# ═══════════════════════════════════════════════════════════════
# EJERCICIO 4.3 — Métricas comparativas
# ═══════════════════════════════════════════════════════════════
"""
┌───────────────────────────────────────┬──────────────────────────┬──────────────────────────────────┐
│ Métrica                               │ Original                 │ Final refactorizado              │
├───────────────────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Nº de funciones/clases                │ 1 (do_stuff)             │ 8 clases + 4 funciones           │
├───────────────────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Complejidad ciclomática               │ ~12-15                   │ ≤3 por función (SRP aplicado)    │
├───────────────────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Complejidad temporal                  │ O(n·m·k)                 │ O(n·m) + O(k) inicialización     │
├───────────────────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Nombres descriptivos                  │ No                       │ Sí                               │
├───────────────────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Testeable por partes                  │ No                       │ Sí (cada función es pura)        │
├───────────────────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ Añadir nuevo tipo de cliente          │ Modificar do_stuff       │ Añadir clase que implemente      │
│                                       │                          │ DiscountStrategy (OCP)           │
└───────────────────────────────────────┴──────────────────────────┴──────────────────────────────────┘
"""

# ═══════════════════════════════════════════════════════════════
# EJERCICIO 4.4 — Post-mortem
# ═══════════════════════════════════════════════════════════════
"""
PUNTOS DONDE LA IA PROPUSO ALGO INCORRECTO O SUBÓPTIMO:

1. NOMENCLATURA: La IA renombró correctamente las variables, pero mantuvo
   dict planos en vez de proponer dataclasses. Hubo que iterar con el prompt
   "convierte los dicts a dataclasses con type hints".

2. OPTIMIZACIÓN: La IA propuso usar `next((i for i in inv if i['id'] == item['id']), None)`
   en vez de pre-indexar. Sigue siendo O(k) por búsqueda. Se le tuvo que indicar
   explícitamente "pre-indexa en dict antes del bucle principal".

3. BUG LÓGICO: La IA NO detectó el bug del elif anidado (bulk dentro de t>1000)
   sin que se le indicara. Solo lo corrigió cuando se especificó en el prompt:
   "revisa si el descuento bulk se aplica independientemente del valor total".

4. PATRÓN STRATEGY: La IA propuso un if/elif directo incluso pidiendo "aplica un
   patrón de diseño". Solo generó Strategy al especificar "Strategy pattern con
   clase base Protocol".

5. LOGGING: La IA mantuvo print() en su primera versión. Solo cambió a logging
   al pedirlo explícitamente en la segunda iteración del prompt.

LIMITACIONES REALES DE LA IA DETECTADAS:
- No razona sobre bugs de control de flujo asíncrono/lógico sin instrucción explícita.
- Tiende a optimizar localmente (mejorar el bucle interno) en vez de globalmente
  (eliminar la necesidad del bucle interno con indexación previa).
- No propone patrones de diseño sin solicitarlos con el nombre exacto.
- La refactorización arquitectural requiere prompts muy específicos; la sintáctica
  (nombres, list comprehensions) la hace bien de forma autónoma.
"""


# ═══════════════════════════════════════════════════════════════
# DEMO Y VERIFICACIÓN
# ═══════════════════════════════════════════════════════════════

def demo_process_orders() -> None:
    print("=" * 65)
    print("BLOQUE 4 — process_orders() refactorizado")
    print("=" * 65)

    inventory = [
        InventoryItem(id=1, price=999.0,  stock=10),
        InventoryItem(id=2, price=29.0,   stock=5),
        InventoryItem(id=3, price=79.0,   stock=0),   # sin stock
        InventoryItem(id=4, price=1500.0, stock=3),
    ]

    discounts = {"premium": 0.10, "vip": 0.20, "bulk": 0.15}

    orders = [
        Order(id=1, type=OrderType.PREMIUM,  items=[OrderItem(1, 1), OrderItem(2, 3)]),
        Order(id=2, type=OrderType.VIP,      items=[OrderItem(4, 1)]),   # > 1000 → +5%
        Order(id=3, type=OrderType.BULK,
              items=[OrderItem(1, 1)] * 12),              # 12 líneas → bulk discount
        Order(id=4, type=OrderType.STANDARD, items=[OrderItem(3, 2), OrderItem(99, 1)]),  # errores
    ]

    results = process_orders(orders, discounts, inventory)

    for r in results:
        status = "✓" if not r.warnings else "⚠"
        print(f"\n  {status} Order {r.order_id}: {r.total}€")
        for w in r.warnings:
            print(f"      ↳ {w}")

    print(f"\n  Total pedidos procesados: {len(results)}")
    print(f"  Complejidad: O(n·m) con n=pedidos, m=líneas/pedido")


def verificar_equivalencia_con_original() -> None:
    """
    Verifica que la versión refactorizada produce los mismos resultados
    que el original para un caso sin bugs (sin bulk con t>1000).
    """
    print("\n" + "=" * 65)
    print("VERIFICACIÓN — Equivalencia con código original")
    print("=" * 65)

    # Replicamos do_stuff original para comparar
    def do_stuff_original(ords, disc, inv):
        res = []
        for o in ords:
            t = 0
            for item in o['items']:
                found = False
                for i in inv:
                    if i['id'] == item['id']:
                        if i['stock'] > 0:
                            t += item['qty'] * i['price']
                            found = True
                            break
            if o['type'] == 'premium':
                t = t * (1 - disc['premium'])
            elif o['type'] == 'vip':
                t = t * (1 - disc['vip'])
            if t > 1000:
                t = t * 0.95
            elif o['type'] == 'bulk':
                if len(o['items']) > 10:
                    t = t * (1 - disc['bulk'])
            res.append({'order_id': o['id'], 'total': round(t, 2)})
        return res

    # Datos de prueba sin casos de borde (bulk con t>1000)
    ords_dict = [
        {'id': 1, 'type': 'premium', 'items': [{'id': 1, 'qty': 1}, {'id': 2, 'qty': 2}]},
        {'id': 2, 'type': 'vip',     'items': [{'id': 2, 'qty': 1}]},
    ]
    inv_dict  = [
        {'id': 1, 'price': 100.0, 'stock': 10},
        {'id': 2, 'price': 50.0,  'stock': 5},
    ]
    disc_dict = {'premium': 0.10, 'vip': 0.20, 'bulk': 0.15}

    orig_results = do_stuff_original(ords_dict, disc_dict, inv_dict)

    # Versión refactorizada con los mismos datos
    inv_new = [InventoryItem(id=i['id'], price=i['price'], stock=i['stock']) for i in inv_dict]
    ords_new = [
        Order(id=1, type=OrderType.PREMIUM, items=[OrderItem(1, 1), OrderItem(2, 2)]),
        Order(id=2, type=OrderType.VIP,     items=[OrderItem(2, 1)]),
    ]
    new_results = process_orders(ords_new, disc_dict, inv_new)

    for orig, new in zip(orig_results, new_results):
        match = "✓" if orig['total'] == new.total else "✗ DIFERENTE"
        print(f"  Order {orig['order_id']}: original={orig['total']}€  "
              f"refactorizado={new.total}€  {match}")


if __name__ == "__main__":
    demo_process_orders()
    verificar_equivalencia_con_original()