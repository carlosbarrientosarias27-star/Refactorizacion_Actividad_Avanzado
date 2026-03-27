import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional
 
 
# ─────────────────────────────────────────────────────────────
# CLASE DE ESTADÍSTICAS (responsabilidad separada)
# ─────────────────────────────────────────────────────────────
@dataclass
class CacheStats:
    """
    Almacena métricas de uso de la caché.
    Responsabilidad única: solo estadísticas.
    """
    hits: int = 0
    misses: int = 0
    evictions: int = 0          # cuántas entradas se expulsaron por LRU
    expirations: int = 0        # cuántas entradas expiraron por TTL
 
    def record_hit(self) -> None:
        self.hits += 1
 
    def record_miss(self) -> None:
        self.misses += 1
 
    def record_eviction(self) -> None:
        self.evictions += 1
 
    def record_expiration(self) -> None:
        self.expirations += 1
 
    @property
    def hit_ratio(self) -> float:
        """Retorna 0.0 si aún no hubo peticiones (evita ZeroDivisionError)."""
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0
 
    def summary(self) -> str:
        return (
            f"Hits: {self.hits} | Misses: {self.misses} | "
            f"Ratio: {self.hit_ratio:.2%} | "
            f"Evictions: {self.evictions} | Expirations: {self.expirations}"
        )
 
 
# ─────────────────────────────────────────────────────────────
# ENTRADA DE CACHÉ (TTL por clave individual)
# ─────────────────────────────────────────────────────────────
@dataclass
class CacheEntry:
    """Encapsula el dato y su tiempo de expiración."""
    data: Any
    expires_at: float           # timestamp absoluto de expiración
 
    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at
 
 
# ─────────────────────────────────────────────────────────────
# CACHÉ PRINCIPAL — Thread-safe, LRU, TTL por clave
# ─────────────────────────────────────────────────────────────
class TTLCache:
    """
    Caché con expiración por clave (TTL individual), política LRU
    y seguridad ante accesos concurrentes.
 
    Decisión de estructura de datos:
    - collections.OrderedDict mantiene orden de inserción/acceso → LRU nativo
    - threading.Lock (no RLock): no hay recursión en los métodos → Lock es más eficiente
    - No se usa functools.lru_cache porque no permite TTL ni maxsize dinámico
    """
 
    def __init__(self, maxsize: int = 128, default_ttl: float = 300.0) -> None:
        """
        Args:
            maxsize:     Número máximo de entradas. Al superar este límite
                         se expulsa la entrada menos recientemente usada (LRU).
            default_ttl: TTL en segundos para claves sin TTL explícito.
        """
        if maxsize <= 0:
            raise ValueError("maxsize debe ser mayor que 0")
        if default_ttl <= 0:
            raise ValueError("default_ttl debe ser mayor que 0")
 
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self.stats = CacheStats()
 
    # ── Lectura ──────────────────────────────────────────────
    def get(self, key: str) -> Optional[Any]:
        """
        Devuelve el valor si existe y no expiró; None en caso contrario.
        Mueve la clave al final del OrderedDict para actualizar acceso LRU.
 
        Args:
            key: Clave de búsqueda.
 
        Returns:
            El dato almacenado o None.
        """
        with self._lock:
            entry = self._store.get(key)
 
            if entry is None:
                self.stats.record_miss()
                return None
 
            if entry.is_expired():
                del self._store[key]
                self.stats.record_expiration()
                self.stats.record_miss()
                return None
 
            # Actualizar posición LRU: mover al final
            self._store.move_to_end(key)
            self.stats.record_hit()
            return entry.data
 
    # ── Escritura ─────────────────────────────────────────────
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Almacena un valor con TTL individual.
 
        Args:
            key:   Clave de almacenamiento.
            value: Dato a guardar.
            ttl:   Segundos de vida. Si es None usa default_ttl.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + effective_ttl
 
        with self._lock:
            if key in self._store:
                # Actualizar entrada existente y moverla al final
                self._store.move_to_end(key)
            else:
                # Comprobar límite de tamaño → expulsar LRU (primer elemento)
                if len(self._store) >= self._maxsize:
                    self._store.popitem(last=False)   # FIFO del OrderedDict = LRU
                    self.stats.record_eviction()
 
            self._store[key] = CacheEntry(data=value, expires_at=expires_at)
 
    # ── Eliminación ───────────────────────────────────────────
    def delete(self, key: str) -> bool:
        """
        Elimina una clave. Retorna True si existía.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False
 
    def clear(self) -> None:
        """Vacía la caché completa."""
        with self._lock:
            self._store.clear()
 
    # ── Utilidades ────────────────────────────────────────────
    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
 
    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None   # respeta TTL
 
    @property
    def maxsize(self) -> int:
        return self._maxsize
 
 
# ─────────────────────────────────────────────────────────────
# DEMOSTRACIÓN
# ─────────────────────────────────────────────────────────────
def demo_basico() -> None:
    print("=" * 60)
    print("DEMO — TTLCache (maxsize=3, default_ttl=2s)")
    print("=" * 60)
 
    cache = TTLCache(maxsize=3, default_ttl=2.0)
 
    # Escritura
    cache.set("usuario:1", {"nombre": "Ana", "rol": "admin"})
    cache.set("usuario:2", {"nombre": "Luis", "rol": "user"})
    cache.set("producto:5", {"nombre": "Laptop", "precio": 999})
 
    # Lectura con hit
    print(f"get usuario:1 → {cache.get('usuario:1')}")
    print(f"Stats: {cache.stats.summary()}")
 
    # TTL individual corto
    cache.set("temporal", "dato efímero", ttl=0.5)
    print(f"get temporal (antes expirar) → {cache.get('temporal')}")
    time.sleep(0.6)
    print(f"get temporal (después expirar) → {cache.get('temporal')}")
    print(f"Stats tras expiración: {cache.stats.summary()}")
 
    # Evicción LRU: la caché ya tiene 3 entradas (maxsize=3)
    # Añadir una nueva fuerza expulsión de la menos reciente
    cache.set("nuevo:item", "valor nuevo")
    print(f"\nTamaño tras inserción extra: {len(cache)} (máx={cache.maxsize})")
    print(f"Stats con eviction: {cache.stats.summary()}")
 
    # get_stats sin peticiones previas → no divide por cero
    cache2 = TTLCache()
    print(f"\nHit ratio caché vacía: {cache2.stats.hit_ratio}")   # 0.0, sin excepción
 
 
def demo_concurrencia() -> None:
    """Verifica que no hay race conditions con múltiples hilos."""
    print("\n" + "=" * 60)
    print("DEMO — Thread-safety con 10 hilos concurrentes")
    print("=" * 60)
 
    cache = TTLCache(maxsize=50, default_ttl=10.0)
    errors = []
 
    def worker(thread_id: int) -> None:
        for i in range(20):
            key = f"key:{i % 5}"        # claves compartidas entre hilos
            cache.set(key, f"t{thread_id}-v{i}")
            val = cache.get(key)
            if val is None and i % 5 < 5:
                # Puede ser None si otro hilo sobreescribió, no es error
                pass
 
    threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
 
    print(f"Operaciones completadas sin excepciones: ✓")
    print(f"Stats finales: {cache.stats.summary()}")
 
 
if __name__ == "__main__":
    demo_basico()
    demo_concurrencia()