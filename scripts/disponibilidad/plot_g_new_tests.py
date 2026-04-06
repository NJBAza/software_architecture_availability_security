"""Graficas para nuevos escenarios G de escalado/rollback."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path("registers/data/test")
OUT = ROOT / "results" / "plots"
plt.style.use("seaborn-v0_8-whitegrid")


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _to_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _save(name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=170)
    plt.close()


def plot_test1() -> None:
    csv = ROOT / "G_escalado_tiempo_respuesta_usuarios" / "results" / "escalado_respuesta.csv"
    df = _load(csv)
    if df.empty:
        return
    df = _to_num(df, ["users", "avg_ms", "p95_ms", "error_pct"])
    df = df.sort_values("users")
    plt.figure(figsize=(9, 5))
    plt.plot(df["users"], df["avg_ms"], marker="o", label="avg_ms")
    plt.plot(df["users"], df["p95_ms"], marker="s", label="p95_ms")
    plt.axhline(y=5000, color="red", linestyle="--", label="umbral_5s")
    plt.xlabel("Usuarios concurrentes (VUS)")
    plt.ylabel("Latencia (ms)")
    plt.title("Test1 - Tiempo de respuesta vs usuarios")
    plt.legend()
    _save("test1_avg_ms_vs_vus.png")


def _plot_test2(csv: Path, title: str, out_name: str) -> None:
    df = _load(csv)
    if df.empty:
        return
    df = _to_num(df, ["users", "conflict_requests", "error_pct", "p95_ms", "rollback_409_count"])
    df = df.sort_values("users")
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(df["users"], df["error_pct"], marker="o", color="#e15759", label="error_pct")
    ax1.set_xlabel("Usuarios concurrentes (VUS)")
    ax1.set_ylabel("Error %", color="#e15759")
    ax2 = ax1.twinx()
    ax2.plot(df["users"], df["p95_ms"], marker="s", color="#4c78a8", label="p95_ms")
    ax2.plot(df["users"], df["rollback_409_count"], marker="^", color="#59a14f", label="rollback_409_count")
    ax2.plot(df["users"], df["conflict_requests"], marker="x", color="#f28e2b", label="conflict_requests")
    ax2.set_ylabel("p95 (ms) / count")
    plt.title(title)
    _save(out_name)


def plot_test2_2() -> None:
    _plot_test2(
        ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_10pct_parejas.csv",
        "Test2.2 - Rollback 10% parejas",
        "test2_2_metrics_vs_vus.png",
    )


def plot_test_rollback_1pct() -> None:
    _plot_test2(
        ROOT / "G_rollback_carga_conflicto_1pct" / "results" / "rollback_1pct.csv",
        "Rollback 1% conflicto - metricas vs usuarios",
        "rollback_1pct_metrics_vs_vus.png",
    )


def plot_test_latencia_escalonada() -> None:
    csv = ROOT / "G_latencia_escalonada_usuarios" / "results" / "latencia_escalonada.csv"
    df = _load(csv)
    if df.empty:
        return
    df = _to_num(df, ["users", "avg_ms", "p95_ms"])
    df = df.sort_values("users")
    plt.figure(figsize=(10, 5))
    plt.plot(df["users"], df["avg_ms"], marker="o", label="avg_ms")
    plt.plot(df["users"], df["p95_ms"], marker="s", label="p95_ms")
    plt.xlabel("Usuarios concurrentes (VUS)")
    plt.ylabel("Latencia (ms)")
    plt.title("Latencia escalonada - tiempo de respuesta vs usuarios")
    plt.legend()
    _save("latencia_escalonada_avg_vs_vus.png")


def main() -> None:
    plot_test1()
    _plot_test2(
        ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_10pct_parejas.csv",
        "G_rollback_carga - metricas vs usuarios",
        "g_rollback_carga_metrics_vs_vus.png",
    )
    plot_test2_2()
    plot_test_rollback_1pct()
    plot_test_latencia_escalonada()
    print("Plots de nuevos tests generados.")


if __name__ == "__main__":
    main()
