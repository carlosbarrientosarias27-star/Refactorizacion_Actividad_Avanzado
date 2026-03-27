"""
BLOQUE 3 — Modernización de código legacy
==========================================
3.1 Callbacks → async/await (con corrección del bug lógico)
3.2 Reverse engineering del código generado por la IA
"""

# NOTA: Este módulo tiene secciones en Python y JavaScript (comentadas).
# El ejercicio 3.1 es JavaScript, lo analizamos en Python con asyncio como equivalente.

import asyncio
from typing import Optional, List
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
# EJERCICIO 3.1 — Bug lógico en el código original de callbacks
# ═══════════════════════════════════════════════════════════════

"""
─────────────────────────────────────────────────────────────────
CÓDIGO ORIGINAL JAVASCRIPT (callback hell):
─────────────────────────────────────────────────────────────────
function getUserData(userId, callback) {
  db.query('SELECT * FROM users WHERE id = ?', [userId], function(err, user) {
    if (err) { callback(err, null); return; }
    db.query('SELECT * FROM orders WHERE user_id = ?', [user.id], function(err, orders) {
      if (err) { callback(err, null); return; }
      orders.forEach(function(order) {
        db.query('SELECT * FROM items WHERE order_id = ?', [order.id], function(err, items) {
          if (err) { callback(err, null); return; }
          order.items = items;
          // ← El callback de error aquí NUNCA llega al caller original
        });
      });
      user.orders = orders;
      callback(null, user);  // ← SE EJECUTA ANTES de que los forEach terminen
    });
  });
}

"""


# ─────────────────────────────────────────────────────────────
# EQUIVALENTE EN PYTHON (asyncio) para ejecutar y demostrar
# ─────────────────────────────────────────────────────────────
@dataclass
class User:
    id: int
    nombre: str
    orders: List["Order"] = field(default_factory=list)

@dataclass
class Order:
    id: int
    user_id: int
    tipo: str
    items: List["Item"] = field(default_factory=list)

@dataclass
class Item:
    id: int
    order_id: int
    nombre: str
    precio: float


# Simulación de base de datos con latencia artificial
async def db_get_user(user_id: int) -> Optional[User]:
    await asyncio.sleep(0.05)  # simula latencia de red
    if user_id == 1:
        return User(id=1, nombre="Ana García")
    return None

async def db_get_orders(user_id: int) -> List[Order]:
    await asyncio.sleep(0.05)
    return [
        Order(id=101, user_id=user_id, tipo="premium"),
        Order(id=102, user_id=user_id, tipo="normal"),
        Order(id=103, user_id=user_id, tipo="bulk"),
    ]

async def db_get_items(order_id: int) -> List[Item]:
    await asyncio.sleep(0.05)  # cada query tarda ~50ms
    items_db = {
        101: [Item(1, 101, "Laptop", 999.0), Item(2, 101, "Ratón", 29.0)],
        102: [Item(3, 102, "Teclado", 79.0)],
        103: [Item(4, 103, "Monitor", 349.0), Item(5, 103, "Silla", 199.0)],
    }
    return items_db.get(order_id, [])


# VERSION CORRECTA: async/await con Promise.all equivalente
async def get_user_data(user_id: int) -> Optional[User]:
    """
    Versión modernizada y corregida del callback original.
    Usa asyncio.gather (≡ Promise.all) para queries de items en paralelo.
    """
    user = await db_get_user(user_id)
    if user is None:
        raise ValueError(f"Usuario {user_id} no encontrado")

    orders = await db_get_orders(user.id)

    # asyncio.gather = Promise.all: lanza todas las queries de items en paralelo
    async def enrich_order(order: Order) -> Order:
        order.items = await db_get_items(order.id)
        return order

    user.orders = list(await asyncio.gather(*[enrich_order(o) for o in orders]))
    return user


async def demo_async() -> None:
    print("=" * 60)
    print("BLOQUE 3.1 — async/await con asyncio.gather")
    print("=" * 60)

    inicio = asyncio.get_event_loop().time()
    user = await get_user_data(1)
    elapsed = asyncio.get_event_loop().time() - inicio

    print(f"\nUsuario: {user.nombre} (id={user.id})")
    print(f"Orders cargadas: {len(user.orders)}")
    for order in user.orders:
        print(f"  Order {order.id} ({order.tipo}): {len(order.items)} items")
        for item in order.items:
            print(f"    - {item.nombre}: {item.precio}€")

    print(f"\nTiempo total: {elapsed:.3f}s")
    print(f"  (3 queries de items en paralelo → ~50ms en vez de ~150ms)")
    print(f"  Ventaja de asyncio.gather sobre secuencial: ~{3 * 0.05 / elapsed:.1f}x")