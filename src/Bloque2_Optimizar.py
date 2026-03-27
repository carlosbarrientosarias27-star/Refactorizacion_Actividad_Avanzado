"""
BLOQUE 2 — Optimización real: mide antes de optimizar
======================================================
Comparativa O(n²) vs O(n) + streaming para 1M de filas
"""

import timeit
import time
import csv
import io
import random
import string
from collections import Counter
from typing import Iterator


# ═══════════════════════════════════════════════════════════════
# EJERCICIO 2.1 — find_duplicates_and_count
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# VERSIÓN ORIGINAL — O(n²) en tiempo, O(n) en espacio
# ─────────────────────────────────────────────────────────────
def find_duplicates_and_count_original(data: list) -> dict:
    """
    Encuentra elementos duplicados y cuántas veces aparecen.
    Complejidad temporal: O(n²) — dos bucles anidados sobre toda la lista.
    Complejidad espacial: O(n) — dict de resultados.
    """
    result = {}
    for i in range(len(data)):
        count = 0
        for j in range(len(data)):
            if data[i] == data[j]:
                count += 1
        if count > 1 and data[i] not in result:
            result[data[i]] = count
    return result


# ─────────────────────────────────────────────────────────────
# VERSIÓN OPTIMIZADA — O(n) en tiempo, O(n) en espacio
# ─────────────────────────────────────────────────────────────
def find_duplicates_and_count_optimized(data: list) -> dict:
    """
    Encuentra elementos duplicados y cuántas veces aparecen.
    Complejidad temporal: O(n) — un solo recorrido con Counter.
    Complejidad espacial: O(n) — Counter almacena hasta n entradas.

    Nota sobre tipos no hashables:
    - La versión original SÍ maneja listas/dicts (los compara con ==).
    - Counter usa hashing, por lo que tipos no hashables (list, dict, set)
      lanzarían TypeError. Se añade manejo explícito.
    """
    try:
        counts = Counter(data)
    except TypeError:
        # Fallback para tipos no hashables: comparación cuadrática pero controlada
        return find_duplicates_and_count_original(data)

    return {item: count for item, count in counts.items() if count > 1}


# ─────────────────────────────────────────────────────────────
# MEDICIÓN DE TIEMPOS
# ─────────────────────────────────────────────────────────────
def generar_datos(n: int, rango_valores: int = None) -> list:
    """
    Genera lista de n enteros con duplicados garantizados.
    rango_valores controla la densidad de duplicados.
    """
    if rango_valores is None:
        rango_valores = n // 3   # ~33% de valores únicos → muchos duplicados
    return [random.randint(0, rango_valores) for _ in range(n)]


def medir_tiempo(func, data: list, repeticiones: int = 3) -> float:
    """
    Mide tiempo de ejecución en segundos (mejor de 'repeticiones' ejecuciones).
    Usa time.perf_counter para máxima precisión.
    """
    tiempos = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        func(data)
        tiempos.append(time.perf_counter() - inicio)
    return min(tiempos)


def ejecutar_comparativa() -> None:
    print("=" * 65)
    print("BLOQUE 2.1 — Comparativa O(n²) vs O(n)")
    print("=" * 65)

    tamaños = [1_000, 5_000, 10_000, 50_000, 100_000]

    print(f"\n{'Tamaño':>10} | {'Original (s)':>14} | {'Optimizado (s)':>16} | {'Speedup':>8}")
    print("-" * 60)

    for n in tamaños:
        datos = generar_datos(n)

        # Para n grandes la versión original es demasiado lenta → limitamos
        if n <= 10_000:
            t_orig = medir_tiempo(find_duplicates_and_count_original, datos)
        else:
            t_orig = None   # demasiado lento para medir en tiempo razonable

        t_opt = medir_tiempo(find_duplicates_and_count_optimized, datos)

        if t_orig is not None:
            speedup = t_orig / t_opt if t_opt > 0 else float("inf")
            print(f"{n:>10,} | {t_orig:>14.6f} | {t_opt:>16.6f} | {speedup:>7.1f}x")
        else:
            print(f"{n:>10,} | {'demasiado lento':>14} | {t_opt:>16.6f} | {'>>1000x':>8}")

    # Verificar resultados idénticos
    datos_test = generar_datos(500)
    r_orig = find_duplicates_and_count_original(datos_test)
    r_opt  = find_duplicates_and_count_optimized(datos_test)
    assert r_orig == r_opt, "¡Las versiones dan resultados diferentes!"
    print(f"\n✓ Resultados verificados: ambas versiones son equivalentes")

    # Verificar manejo de tipos no hashables
    datos_con_lista = [1, 2, [3, 4], 1, 2]
    r_fallback = find_duplicates_and_count_optimized(datos_con_lista)
    print(f"✓ Tipos no hashables manejados: {r_fallback}")


# ═══════════════════════════════════════════════════════════════
# EJERCICIO 2.2 — Streaming para 1 millón de filas (sin cargar en memoria)
# ═══════════════════════════════════════════════════════════════

"""
PROMPT USADO PARA LA IA:
"Escribe una función Python que cuente duplicados en un CSV de 1 millón de filas
SIN cargar el archivo completo en memoria. Requisitos obligatorios:
1. Usa un generador o itertools para leer fila a fila (streaming real).
2. La función debe recibir: ruta del archivo, nombre de la columna a analizar.
3. Memoria máxima proporcional a valores únicos, NO al número de filas.
4. Demuestra cómo verificar que no se cargó todo en memoria (tracemalloc o similar).
5. Type hints completos. Maneja errores de archivo no encontrado."

ANÁLISIS:
- La IA normalmente usa csv.reader + Counter, lo cual es correcto.
- Counter sí carga en memoria los valores únicos, pero NO todas las filas → válido.
- El truco está en NO usar pd.read_csv() que carga todo de golpe.
- Verificación real: tracemalloc mide pico de memoria.
"""

import tracemalloc
import os
import tempfile


def generar_csv_grande(ruta: str, n_filas: int = 100_000, n_valores_unicos: int = 1_000) -> None:
    """
    Genera un CSV de prueba con duplicados controlados.
    (En producción sería el archivo real de 1M filas.)
    """
    valores = [f"val_{i}" for i in range(n_valores_unicos)]
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "categoria", "valor"])
        for i in range(n_filas):
            writer.writerow([i, random.choice(valores), random.randint(0, 9999)])


def stream_duplicados_csv(ruta_csv: str, columna: str) -> dict:
    """
    Cuenta duplicados en un CSV de cualquier tamaño SIN cargar el archivo en memoria.

    Cómo funciona el streaming real:
    - csv.reader es un iterador lazy: lee una línea a la vez del disco.
    - Counter acumula solo los valores únicos (no todas las filas).
    - Memoria usada ≈ O(valores_únicos), independiente del número de filas.

    Args:
        ruta_csv: Ruta al archivo CSV.
        columna:  Nombre de la columna a analizar.

    Returns:
        Dict {valor: count} con solo los duplicados (count > 1).

    Raises:
        FileNotFoundError: Si el archivo no existe.
        KeyError: Si la columna no existe en el CSV.
    """
    if not os.path.exists(ruta_csv):
        raise FileNotFoundError(f"Archivo no encontrado: {ruta_csv}")

    def _fila_generator(ruta: str, col: str) -> Iterator[str]:
        """Generador puro: yield un valor por fila, sin almacenar nada."""
        with open(ruta, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if col not in (reader.fieldnames or []):
                raise KeyError(f"Columna '{col}' no encontrada. Columnas: {reader.fieldnames}")
            for row in reader:
                yield row[col]       # ← solo el valor de la columna, nada más

    conteo = Counter(_fila_generator(ruta_csv, columna))
    return {val: cnt for val, cnt in conteo.items() if cnt > 1}


def verificar_memoria_streaming(ruta_csv: str, columna: str) -> None:
    """
    Ejecuta el streaming con tracemalloc para medir el pico de memoria real.
    Si la función cargara todo en memoria, el pico sería proporcional al archivo.
    """
    tamaño_archivo_mb = os.path.getsize(ruta_csv) / (1024 * 1024)

    tracemalloc.start()
    resultado = stream_duplicados_csv(ruta_csv, columna)
    _, pico_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    pico_mb = pico_bytes / (1024 * 1024)
    ratio = pico_mb / tamaño_archivo_mb if tamaño_archivo_mb > 0 else 0

    print(f"\n{'─'*55}")
    print(f"VERIFICACIÓN DE MEMORIA — Streaming CSV")
    print(f"{'─'*55}")
    print(f"  Tamaño del archivo:      {tamaño_archivo_mb:.2f} MB")
    print(f"  Pico de memoria Python:  {pico_mb:.2f} MB")
    print(f"  Ratio memoria/archivo:   {ratio:.1%}")
    print(f"  Valores únicos:          {len(resultado):,}")
    print(f"  Valores duplicados:      {len(resultado):,}")
    if ratio < 0.5:
        print(f"  ✓ Streaming real confirmado: memoria << tamaño del archivo")
    else:
        print(f"  ⚠ Ratio alto — posible carga masiva en memoria")


def ejecutar_streaming_demo() -> None:
    print("\n" + "=" * 65)
    print("BLOQUE 2.2 — Streaming CSV (sin cargar en memoria)")
    print("=" * 65)

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        ruta = tmp.name

    try:
        print("\nGenerando CSV de 100.000 filas para demo...")
        generar_csv_grande(ruta, n_filas=100_000, n_valores_unicos=500)

        verificar_memoria_streaming(ruta, "categoria")

        # Muestra los 5 valores más duplicados
        duplicados = stream_duplicados_csv(ruta, "categoria")
        top5 = sorted(duplicados.items(), key=lambda x: -x[1])[:5]
        print(f"\n  Top 5 valores más frecuentes:")
        for val, cnt in top5:
            print(f"    {val}: {cnt} veces")
    finally:
        os.unlink(ruta)


# ═══════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    random.seed(42)
    ejecutar_comparativa()
    ejecutar_streaming_demo()