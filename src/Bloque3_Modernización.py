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



# ═══════════════════════════════════════════════════════════════
# EJERCICIO 3.2 — Reverse engineering del código generado por la IA
# ═══════════════════════════════════════════════════════════════
 
"""
─────────────────────────────────────────────────────────────────
ANÁLISIS DEL CÓDIGO GENERADO POR LA IA:
─────────────────────────────────────────────────────────────────
 
from dataclasses import dataclass
from typing import Protocol, List
from abc import abstractmethod

class Validator(Protocol):
    @abstractmethod
    def validate(self, value: str) -> bool: ...
    @abstractmethod
    def error_message(self) -> str: ...

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]

class FormValidator:
    def __init__(self, validators: List[Validator]):
        self.validators = validators

    def validate_all(self, value: str) -> ValidationResult:
        errors = [v.error_message() for v in self.validators if not v.validate(value)]
        return ValidationResult(not errors, errors)
"""
 

import asyncio
from typing import Protocol, List, runtime_checkable
from dataclasses import dataclass
 

# ─── VERSIÓN CORREGIDA ────────────────────────────────────────
 
@runtime_checkable
class Validator(Protocol):
    """
    Define la interfaz estructural de un validador.
    NO se usa @abstractmethod: Protocol ya garantiza el contrato.
    @runtime_checkable permite usar isinstance(obj, Validator).
    """
    def validate(self, value: str) -> bool: ...
    def error_message(self) -> str: ...
 
 
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
 
    def __str__(self) -> str:
        if self.is_valid:
            return "✓ Válido"
        return f"✗ Errores: {'; '.join(self.errors)}"
 
 
class FormValidator:
    """Orquesta múltiples Validators aplicando todos sobre un valor."""
 
    def __init__(self, validators: List[Validator]) -> None:
        self._validators = validators
 
    def validate_all(self, value: str) -> ValidationResult:
        errors = [v.error_message() for v in self._validators if not v.validate(value)]
        return ValidationResult(is_valid=not errors, errors=errors)
 
 
# Implementaciones concretas (duck-typing: no necesitan heredar de Validator)
class LongitudMinima:
    def __init__(self, minimo: int) -> None:
        self._minimo = minimo
    def validate(self, value: str) -> bool:
        return len(value) >= self._minimo
    def error_message(self) -> str:
        return f"Longitud mínima: {self._minimo} caracteres"
 
class NoContienePalabraProhibida:
    def __init__(self, palabra: str) -> None:
        self._palabra = palabra
    def validate(self, value: str) -> bool:
        return self._palabra.lower() not in value.lower()
    def error_message(self) -> str:
        return f"No debe contener '{self._palabra}'"
 
class EsAlfanumerico:
    def validate(self, value: str) -> bool:
        return value.isalnum()
    def error_message(self) -> str:
        return "Solo caracteres alfanuméricos"
 
 
def demo_validacion() -> None:
    print("\n" + "=" * 60)
    print("BLOQUE 3.2 — Sistema de validación refactorizado")
    print("=" * 60)
 
    validador = FormValidator([
        LongitudMinima(6),
        NoContienePalabraProhibida("admin"),
        EsAlfanumerico(),
    ])
 
    casos = ["abc", "admin123", "usuario!", "Correcto99"]
    for caso in casos:
        resultado = validador.validate_all(caso)
        print(f"  '{caso}': {resultado}")
 
    # Verificar que Protocol funciona con isinstance (gracias a @runtime_checkable)
    longitud = LongitudMinima(5)
    print(f"\n  isinstance(LongitudMinima(), Validator): {isinstance(longitud, Validator)}")
 
 
# ═══════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    asyncio.run(demo_async())
    demo_validacion()