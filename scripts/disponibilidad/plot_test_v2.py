"""Graficas test_v2 — estilo moderno sin bordes."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path("registers/data/test_v2")
OUT = ROOT / "results" / "plots"

for spine in ["top", "right", "left", "bottom"]:
    plt.rcParams[f"axes.spines.{spine}"] = False
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3
plt.rcParams["font.size"] = 11


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _save(name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=170, bbox_inches="tight")
    plt.close()
    print(f"  -> {OUT / name}")


# ─── Bloque 1: Concurrencia sin conflictos ─────────────────────────────────

def plot_concurrencia() -> None:
    df = _read(ROOT / "concurrencia_sin_conflicto" / "results" / "resumen.csv")
    if df.empty:
        return
    df = _num(df, ["nivel", "avg_ms", "p95_ms", "max_ms", "error_pct"])
    df = df.sort_values("nivel")

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(df["nivel"], df["avg_ms"], marker="o", linewidth=2, label="avg_ms")
    ax1.plot(df["nivel"], df["p95_ms"], marker="s", linewidth=2, label="p95_ms")
    ax1.plot(df["nivel"], df["max_ms"], marker="^", linewidth=2, label="max_ms")
    ax1.set_xlabel("Solicitudes")
    ax1.set_ylabel("Latencia (ms)")
    ax1.set_xscale("log")
    ax1.legend()
    plt.title("Concurrencia sin conflictos — Latencia vs solicitudes")
    _save("concurrencia_latencia.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df["nivel"].astype(str), df["error_pct"], color="#e15759", width=0.6)
    ax.set_xlabel("Solicitudes")
    ax.set_ylabel("Error %")
    plt.title("Concurrencia sin conflictos — Tasa de error")
    _save("concurrencia_error_pct.png")


# ─── Bloque 2a: Dos clientes conflicto ──────────────────────────────────────

def plot_dos_clientes() -> None:
    df = _read(ROOT / "dos_clientes_conflicto" / "results" / "detalle.csv")
    if df.empty:
        return
    df = _num(df, ["duracion_ns", "http_status"])
    df["duracion_ns"] = df["duracion_ns"].astype(float)

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#4c78a8" if s == 200 else "#e15759" for s in df["http_status"]]
    bars = ax.bar(range(len(df)), df["duracion_ns"], color=colors, width=0.6)
    ax.set_xlabel("Solicitud")
    ax.set_ylabel("Duracion (nanosegundos)")
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels([f"HTTP {s}" for s in df["http_status"]])

    for bar, ns in zip(bars, df["duracion_ns"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{ns:,.0f} ns", ha="center", va="bottom", fontsize=9)

    plt.title("Dos clientes mismo producto — Duracion en nanosegundos")
    _save("dos_clientes_nanosegundos.png")


# ─── Bloque 2b: Rollback 1% parejas ─────────────────────────────────────────

def plot_rollback_parejas() -> None:
    df = _read(ROOT / "rollback_1pct_parejas" / "results" / "resumen.csv")
    if df.empty:
        return
    df = _num(df, ["nivel", "parejas_conflicto", "rollback_exitosos", "rollback_fallidos", "avg_ms", "p95_ms", "max_ms"])
    df = df.sort_values("nivel")

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(df["nivel"], df["rollback_exitosos"], marker="o", linewidth=2, color="#59a14f", label="Rollback exitosos")
    ax1.plot(df["nivel"], df["rollback_fallidos"], marker="x", linewidth=2, color="#e15759", label="Rollback fallidos")
    ax1.plot(df["nivel"], df["parejas_conflicto"], marker="s", linewidth=2, color="#4c78a8", linestyle="--", label="Parejas conflicto")
    ax1.set_xlabel("Solicitudes totales")
    ax1.set_ylabel("Cantidad")
    ax1.set_xscale("log")
    ax1.legend()
    plt.title("Rollback 1% parejas — Exitosos vs fallidos")
    _save("rollback_parejas_exitosos.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["nivel"], df["avg_ms"], marker="o", linewidth=2, label="avg_ms")
    ax.plot(df["nivel"], df["p95_ms"], marker="s", linewidth=2, label="p95_ms")
    ax.plot(df["nivel"], df["max_ms"], marker="^", linewidth=2, label="max_ms")
    ax.set_xlabel("Solicitudes totales")
    ax.set_ylabel("Latencia (ms)")
    ax.set_xscale("log")
    ax.legend()
    plt.title("Rollback 1% parejas — Latencia")
    _save("rollback_parejas_latencia.png")


# ─── Bloque 3a: Un usuario peligroso ────────────────────────────────────────

def plot_un_peligroso() -> None:
    df = _read(ROOT / "deteccion_un_peligroso" / "results" / "detalle.csv")
    if df.empty:
        return
    df = _num(df, ["duracion_ms", "riesgo"])
    if df.empty:
        return
    row = df.iloc[-1]
    fig, ax = plt.subplots(figsize=(6, 4))
    color = "#59a14f" if float(row.get("duracion_ms", 999)) < 300 else "#e15759"
    ax.barh(["Deteccion"], [row["duracion_ms"]], color=color, height=0.4)
    ax.axvline(x=300, color="#e15759", linestyle="--", label="Umbral 300ms")
    ax.set_xlabel("Duracion (ms)")
    ax.legend()
    plt.title(f"Deteccion usuario peligroso — riesgo={row.get('riesgo', '?')}")
    _save("un_peligroso_tiempo.png")


# ─── Bloque 3b: 1% peligrosos a escala ──────────────────────────────────────

def plot_1pct_peligrosos() -> None:
    df = _read(ROOT / "deteccion_1pct_peligrosos" / "results" / "resumen.csv")
    if df.empty:
        return
    df = _num(df, ["nivel", "deteccion_correcta_pct", "avg_ms", "p95_ms", "en_menos_300ms_pct"])
    df = df.sort_values("nivel")

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(df["nivel"], df["deteccion_correcta_pct"], marker="o", linewidth=2, color="#59a14f", label="Deteccion correcta %")
    ax1.plot(df["nivel"], df["en_menos_300ms_pct"], marker="s", linewidth=2, color="#4c78a8", label="En <300ms %")
    ax1.set_xlabel("Usuarios totales")
    ax1.set_ylabel("%")
    ax1.set_xscale("log")
    ax1.legend()
    plt.title("1% peligrosos — Precision y velocidad de deteccion")
    _save("1pct_peligrosos_precision.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["nivel"], df["avg_ms"], marker="o", linewidth=2, label="avg_ms")
    ax.plot(df["nivel"], df["p95_ms"], marker="s", linewidth=2, label="p95_ms")
    ax.axhline(y=300, color="#e15759", linestyle="--", label="Umbral 300ms")
    ax.set_xlabel("Usuarios totales")
    ax.set_ylabel("Latencia (ms)")
    ax.set_xscale("log")
    ax.legend()
    plt.title("1% peligrosos — Latencia IDS")
    _save("1pct_peligrosos_latencia.png")


# ─── Bloque 3c: 1 condicion individual ──────────────────────────────────────

def plot_1_condicion() -> None:
    df = _read(ROOT / "deteccion_1_condicion" / "results" / "resumen.csv")
    if df.empty:
        return
    df = _num(df, ["nivel", "deteccion_correcta_pct", "falsos_positivos", "avg_ms"])

    for cond in df["condiciones"].unique():
        sub = df[df["condiciones"] == cond].sort_values("nivel")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(sub["nivel"], sub["avg_ms"], marker="o", linewidth=2, label="avg_ms")
        ax.plot(sub["nivel"], sub["deteccion_correcta_pct"], marker="s", linewidth=2, label="Deteccion correcta %")
        ax.set_xlabel("Solicitudes")
        ax.set_ylabel("ms / %")
        ax.set_xscale("log")
        ax.legend()
        plt.title(f"1 condicion: {cond} — Latencia y precision")
        _save(f"1_condicion_{cond}.png")


# ─── Bloque 3d: 2 condiciones combinadas ────────────────────────────────────

def plot_2_condiciones() -> None:
    df = _read(ROOT / "deteccion_2_condiciones" / "results" / "resumen.csv")
    if df.empty:
        return
    df = _num(df, ["nivel", "deteccion_correcta_pct", "avg_ms", "en_menos_300ms_pct"])

    for combo in df["condiciones"].unique():
        sub = df[df["condiciones"] == combo].sort_values("nivel")
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax1.plot(sub["nivel"], sub["deteccion_correcta_pct"], marker="o", linewidth=2, color="#59a14f", label="Deteccion correcta %")
        ax1.plot(sub["nivel"], sub["en_menos_300ms_pct"], marker="s", linewidth=2, color="#4c78a8", label="En <300ms %")
        ax1.set_xlabel("Solicitudes")
        ax1.set_ylabel("%")
        ax1.set_xscale("log")
        ax1.legend()
        plt.title(f"2 condiciones: {combo}")
        _save(f"2_condiciones_{combo.replace('+', '_')}.png")


# ─── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"\nGenerando graficas en: {OUT}")
    plot_concurrencia()
    plot_dos_clientes()
    plot_rollback_parejas()
    plot_un_peligroso()
    plot_1pct_peligrosos()
    plot_1_condicion()
    plot_2_condiciones()
    print("Graficas test_v2 generadas.")


if __name__ == "__main__":
    main()
