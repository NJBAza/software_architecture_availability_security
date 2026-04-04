"""Generacion unificada de graficas para todos los escenarios G."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path("registers/data/test")
OUT = ROOT / "results" / "plots"

plt.style.use("seaborn-v0_8-whitegrid")


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
    plt.savefig(OUT / name, dpi=170)
    plt.close()
    print(f"  -> guardado: {OUT / name}")


# ---------------------------------------------------------------------------
# G_mismo — distribución de estados HTTP
# ---------------------------------------------------------------------------

def plot_g_mismo() -> None:
    df = _read(ROOT / "G_concurrencia_mismo_stock/results/g_concurrencia_mismo_stock.csv")
    if df.empty:
        return
    counts = df["http_status"].astype(str).value_counts().sort_index()
    ax = counts.plot(kind="bar", title="G_mismo - Distribucion de estados HTTP", color="#4c78a8")
    ax.set_ylabel("Cantidad")
    ax.set_xlabel("HTTP status")
    _save("g_mismo_status.png")


# ---------------------------------------------------------------------------
# G_diez — mismo producto por niveles de solicitudes
# ---------------------------------------------------------------------------

def plot_g_diez() -> None:
    df = _read(ROOT / "G_diez_parejas_diez_productos/results/g_diez_parejas.csv")
    if df.empty:
        return
    df = _num(df, ["solicitudes", "success", "errors", "rollback_409_count", "avg_ms", "p95_ms", "max_ms"])
    if "solicitudes" not in df.columns:
        print("  [skip] g_diez: columna 'solicitudes' no encontrada (CSV con formato antiguo)")
        return
    d = df.sort_values("solicitudes")
    plt.figure(figsize=(10, 5))
    plt.plot(d["solicitudes"], d["avg_ms"], marker="o", label="avg_ms")
    plt.plot(d["solicitudes"], d["p95_ms"], marker="s", label="p95_ms")
    plt.plot(d["solicitudes"], d["max_ms"], marker="^", label="max_ms")
    plt.xlabel("Solicitudes")
    plt.ylabel("Latencia (ms)")
    plt.title("G_diez - Mismo producto sin trafico de fondo")
    plt.legend()
    _save("g_diez_same_product_latency.png")


# ---------------------------------------------------------------------------
# G_rollback — latencia de intentos conflictivos
# ---------------------------------------------------------------------------

def plot_g_rollback() -> None:
    df = _read(ROOT / "G_rollback_y_tiempo/results/g_rollback_tiempo.csv")
    if df.empty:
        return
    intentos = df[df["fase"] == "intento"].copy()
    if intentos.empty:
        return
    intentos["duracion_ms"] = pd.to_numeric(intentos["duracion_ms"], errors="coerce")
    ax = intentos["duracion_ms"].plot(
        kind="bar",
        title="G_rollback - Latencia de intentos conflictivos",
        color="#e15759",
    )
    ax.set_ylabel("ms")
    ax.set_xlabel("Intento")
    _save("g_rollback_latency.png")


# ---------------------------------------------------------------------------
# G_capacidad — RPS, p95, avg_ms_per_user y max_ms
# ---------------------------------------------------------------------------

def plot_g_capacidad() -> None:
    df = _read(ROOT / "G_capacidad_usuarios_concurrentes/results/g_capacidad.csv")
    if df.empty:
        return
    df = _num(df, ["vus", "requests", "duracion_s", "rps", "error_pct", "p95_ms", "avg_ms_per_user", "max_ms"])
    df_sorted = df.sort_values("vus")
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(df_sorted["vus"], df_sorted["rps"], marker="o", label="RPS", color="#4c78a8")
    ax1.set_xlabel("Usuarios concurrentes (VUS)")
    ax1.set_ylabel("RPS")
    ax2 = ax1.twinx()
    ax2.plot(df_sorted["vus"], df_sorted["p95_ms"], marker="s", color="#f28e2b", label="p95_ms")
    if "avg_ms_per_user" in df_sorted.columns:
        ax2.plot(df_sorted["vus"], df_sorted["avg_ms_per_user"], marker="^", color="#59a14f", label="avg_ms_per_user")
    if "max_ms" in df_sorted.columns:
        ax2.plot(df_sorted["vus"], df_sorted["max_ms"], marker="x", color="#e15759", label="max_ms")
    ax2.set_ylabel("Latencia (ms)")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    plt.title("G_capacidad - RPS vs Latencia")
    _save("g_capacidad_rps_p95_avgperuser_min.png")


# ---------------------------------------------------------------------------
# G_escalado — tiempo de respuesta vs usuarios (GET /health)
# ---------------------------------------------------------------------------

def plot_g_escalado() -> None:
    csv = ROOT / "G_escalado_tiempo_respuesta_usuarios" / "results" / "escalado_respuesta.csv"
    df = _read(csv)
    if df.empty:
        return
    df = _num(df, ["users", "avg_ms", "p95_ms", "max_ms", "error_pct"])
    if "users" not in df.columns:
        print("  [skip] g_escalado: columna 'users' no encontrada (CSV con formato antiguo)")
        return
    df = df.sort_values("users")
    plt.figure(figsize=(9, 5))
    plt.plot(df["users"], df["avg_ms"], marker="o", label="avg_ms")
    plt.plot(df["users"], df["p95_ms"], marker="s", label="p95_ms")
    plt.axhline(y=5000, color="red", linestyle="--", label="umbral_5s")
    plt.xlabel("Usuarios concurrentes (VUS)")
    plt.ylabel("Latencia (ms)")
    plt.title("G_escalado - Tiempo de respuesta vs usuarios (GET /health)")
    plt.legend()
    _save("g_escalado_avg_ms_vs_vus.png")


# ---------------------------------------------------------------------------
# Helper para plots de rollback: error_pct + rollback_409 + conflict_requests
# ---------------------------------------------------------------------------

def _plot_rollback(csv: Path, title: str, out_name: str) -> None:
    df = _read(csv)
    if df.empty:
        return
    df = _num(df, ["users", "conflict_requests", "error_pct", "p95_ms", "rollback_409_count"])
    if "users" not in df.columns:
        print(f"  [skip] {out_name}: columna 'users' no encontrada")
        return
    df = df.sort_values("users")
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(df["users"], df["error_pct"], marker="o", color="#e15759", label="error_pct")
    ax1.set_xlabel("Usuarios (VUS)")
    ax1.set_ylabel("Error %", color="#e15759")
    ax2 = ax1.twinx()
    ax2.plot(df["users"], df["p95_ms"], marker="s", color="#4c78a8", label="p95_ms")
    ax2.plot(df["users"], df["rollback_409_count"], marker="^", color="#59a14f", label="rollback_409")
    if "conflict_requests" in df.columns:
        ax2.plot(df["users"], df["conflict_requests"], marker="x", color="#f28e2b", label="conflict_requests")
    ax2.set_ylabel("p95 (ms) / count")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    plt.title(title)
    _save(out_name)


# ---------------------------------------------------------------------------
# G_rollback_carga — unificado
# ---------------------------------------------------------------------------

def plot_g_rollback_carga() -> None:
    _plot_rollback(
        ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_10pct_parejas.csv",
        "G_rollback_carga - error_pct y rollback_409 vs usuarios",
        "g_rollback_carga_metrics_vs_vus.png",
    )


# ---------------------------------------------------------------------------
# G_rollback_carga_10pct_parejas
# ---------------------------------------------------------------------------

def plot_g_rollback_10pct_parejas() -> None:
    _plot_rollback(
        ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_10pct_parejas.csv",
        "G_rollback_10pct_parejas - metricas vs usuarios",
        "g_rollback_10pct_parejas_metrics_vs_vus.png",
    )


# ---------------------------------------------------------------------------
# G_rollback_carga_1pct
# ---------------------------------------------------------------------------

def plot_g_rollback_1pct() -> None:
    _plot_rollback(
        ROOT / "G_rollback_carga_conflicto_1pct" / "results" / "rollback_1pct.csv",
        "G_rollback_1pct - metricas vs usuarios",
        "g_rollback_1pct_metrics_vs_vus.png",
    )


# ---------------------------------------------------------------------------
# G_latencia_escalonada — GET /health por niveles
# ---------------------------------------------------------------------------

def plot_g_latencia_escalonada() -> None:
    csv = ROOT / "G_latencia_escalonada_usuarios" / "results" / "latencia_escalonada.csv"
    df = _read(csv)
    if df.empty:
        return
    df = _num(df, ["users", "avg_ms", "p95_ms", "max_ms"])
    if "users" not in df.columns:
        print("  [skip] latencia_escalonada: columna 'users' no encontrada")
        return
    df = df.sort_values("users")
    plt.figure(figsize=(10, 5))
    plt.plot(df["users"], df["avg_ms"], marker="o", label="avg_ms")
    plt.plot(df["users"], df["p95_ms"], marker="s", label="p95_ms")
    if "max_ms" in df.columns:
        plt.plot(df["users"], df["max_ms"], marker="^", label="max_ms")
    plt.xlabel("Usuarios concurrentes (VUS)")
    plt.ylabel("Latencia (ms)")
    plt.title("G_latencia_escalonada - Tiempo de respuesta GET /health vs usuarios")
    plt.legend()
    _save("g_latencia_escalonada_avg_vs_vus.png")


# ---------------------------------------------------------------------------
# G_estocastico — rpm_objetivo vs rpm_real, avg_ms y error_pct
# ---------------------------------------------------------------------------

def plot_g_estocastico() -> None:
    csv = ROOT / "G_estocastico_llegada_usuarios" / "results" / "estocastico.csv"
    df = _read(csv)
    if df.empty:
        return
    df = _num(df, ["rpm_objetivo", "rpm_real", "avg_ms", "p95_ms", "max_ms", "error_pct", "success", "errors"])
    if "rpm_objetivo" not in df.columns:
        print("  [skip] estocastico: columna 'rpm_objetivo' no encontrada")
        return
    df = df.sort_values("rpm_objetivo")

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(df["rpm_objetivo"], df["rpm_real"], marker="o", color="#4c78a8", label="rpm_real")
    ax1.plot(df["rpm_objetivo"], df["rpm_objetivo"], linestyle="--", color="#aaaaaa", label="rpm_objetivo (ideal)")
    ax1.set_xlabel("rpm objetivo")
    ax1.set_ylabel("rpm real alcanzado")

    ax2 = ax1.twinx()
    ax2.plot(df["rpm_objetivo"], df["avg_ms"], marker="s", color="#f28e2b", label="avg_ms")
    ax2.plot(df["rpm_objetivo"], df["error_pct"], marker="^", color="#e15759", label="error_pct")
    ax2.set_ylabel("avg_ms / error_pct")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    plt.title("G_estocastico - Tasa de llegada real vs objetivo y latencia")
    _save("g_estocastico_rpm_vs_latencia.png")


# ---------------------------------------------------------------------------
# main — ejecutar todos los plots
# ---------------------------------------------------------------------------

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"\nGenerando graficas en: {OUT}")
    plot_g_mismo()
    plot_g_diez()
    plot_g_rollback()
    plot_g_capacidad()
    plot_g_escalado()
    plot_g_rollback_carga()
    plot_g_rollback_10pct_parejas()
    plot_g_rollback_1pct()
    plot_g_latencia_escalonada()
    plot_g_estocastico()
    print("Plots generados.")


if __name__ == "__main__":
    main()
