"""Orquestador de pruebas test_v2: concurrencia, disponibilidad y seguridad."""

from __future__ import annotations

import argparse
import time

from scripts.disponibilidad.test_v2 import (
    cmd_concurrencia_sin_conflicto,
    cmd_deteccion_1_condicion,
    cmd_deteccion_1pct_peligrosos,
    cmd_deteccion_2_condiciones,
    cmd_deteccion_un_peligroso,
    cmd_dos_clientes_conflicto,
    cmd_rollback_1pct_parejas,
)


def _timed(name: str, fn) -> None:
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")
    t0 = time.perf_counter()
    try:
        fn()
        dur = time.perf_counter() - t0
        print(f"\n  [{name}] completado en {dur:.1f}s")
    except Exception as e:
        dur = time.perf_counter() - t0
        print(f"\n  [{name}] ERROR en {dur:.1f}s: {e}")


def main() -> None:
    p = argparse.ArgumentParser(description="Ejecutar pruebas test_v2")
    p.add_argument("--solo", type=str, default="", help="Solo un bloque: concurrencia, disponibilidad, seguridad")
    p.add_argument("--skip-plots", action="store_true", help="No generar graficas al final")
    args = p.parse_args()
    solo = args.solo.strip().lower()

    print("\n" + "=" * 70)
    print("  PRUEBAS TEST V2: CONCURRENCIA, DISPONIBILIDAD Y SEGURIDAD")
    print("=" * 70)

    if not solo or solo == "concurrencia":
        _timed("Bloque 1: Concurrencia sin conflictos", cmd_concurrencia_sin_conflicto)

    if not solo or solo == "disponibilidad":
        _timed("Bloque 2a: Dos clientes mismo producto", cmd_dos_clientes_conflicto)
        _timed("Bloque 2b: Rollback 1% parejas", cmd_rollback_1pct_parejas)

    if not solo or solo == "seguridad":
        _timed("Bloque 3a: Un usuario peligroso <300ms", cmd_deteccion_un_peligroso)
        _timed("Bloque 3b: 1% peligrosos a escala", cmd_deteccion_1pct_peligrosos)
        _timed("Bloque 3c: 1 condicion individual", cmd_deteccion_1_condicion)
        _timed("Bloque 3d: 2 condiciones combinadas", cmd_deteccion_2_condiciones)

    if not args.skip_plots:
        try:
            from scripts.disponibilidad.plot_test_v2 import main as plot_main
            print(f"\n{'='*70}")
            print("  GENERANDO GRAFICAS")
            print(f"{'='*70}")
            plot_main()
        except Exception as e:
            print(f"\n[plots] Error al generar graficas: {e}")

    print(f"\n{'='*70}")
    print("  PRUEBAS TEST V2 FINALIZADAS")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
