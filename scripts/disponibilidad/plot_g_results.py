from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path("registers/data/test")
OUT = ROOT / "results" / "plots"
OUT.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df


def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=170)
    plt.close()


# G_mismo
df = _read_csv(ROOT / "G_concurrencia_mismo_stock/results/g_concurrencia_mismo_stock.csv")
if not df.empty:
    counts = df["http_status"].astype(str).value_counts().sort_index()
    ax = counts.plot(kind="bar", title="G_mismo - Distribucion de estados HTTP", color="#4c78a8")
    ax.set_ylabel("Cantidad")
    ax.set_xlabel("HTTP status")
    savefig("g_mismo_status.png")


# G_diez (mismo producto por niveles de solicitudes)
df = _read_csv(ROOT / "G_diez_parejas_diez_productos/results/g_diez_parejas.csv")
if not df.empty:
    for c in ["solicitudes", "success", "errors", "rollback_409_count", "avg_ms", "p95_ms", "min_ms"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    d = df.sort_values("solicitudes")
    plt.figure(figsize=(10, 5))
    plt.plot(d["solicitudes"], d["avg_ms"], marker="o", label="avg_ms")
    plt.plot(d["solicitudes"], d["p95_ms"], marker="s", label="p95_ms")
    plt.plot(d["solicitudes"], d["min_ms"], marker="^", label="min_ms")
    plt.xlabel("Solicitudes")
    plt.ylabel("Latencia (ms)")
    plt.title("G_diez - Mismo producto sin trafico de fondo")
    plt.legend()
    savefig("g_diez_same_product_latency.png")


# G_rollback
df = _read_csv(ROOT / "G_rollback_y_tiempo/results/g_rollback_tiempo.csv")
if not df.empty:
    intentos = df[df["fase"] == "intento"].copy()
    if not intentos.empty:
        intentos["duracion_ms"] = pd.to_numeric(intentos["duracion_ms"], errors="coerce")
        ax = intentos["duracion_ms"].plot(kind="bar", title="G_rollback - Latencia de intentos conflictivos", color="#e15759")
        ax.set_ylabel("ms")
        ax.set_xlabel("Intento")
        savefig("g_rollback_latency.png")


# G_capacidad
df = _read_csv(ROOT / "G_capacidad_usuarios_concurrentes/results/g_capacidad.csv")
if not df.empty:
    for c in ["vus", "requests", "duracion_s", "rps", "error_pct", "p95_ms", "avg_ms_per_user", "min_ms"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df_sorted = df.sort_values("vus")
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(df_sorted["vus"], df_sorted["rps"], marker="o", label="RPS", color="#4c78a8")
    ax1.set_xlabel("Usuarios concurrentes (VUS)")
    ax1.set_ylabel("RPS")
    ax2 = ax1.twinx()
    ax2.plot(df_sorted["vus"], df_sorted["p95_ms"], marker="s", color="#f28e2b", label="p95_ms")
    if "avg_ms_per_user" in df_sorted.columns:
        ax2.plot(df_sorted["vus"], df_sorted["avg_ms_per_user"], marker="^", color="#59a14f", label="avg_ms_per_user")
    if "min_ms" in df_sorted.columns:
        ax2.plot(df_sorted["vus"], df_sorted["min_ms"], marker="x", color="#e15759", label="min_ms")
    ax2.set_ylabel("Latencia")
    plt.title("G_capacidad - RPS vs p95")
    savefig("g_capacidad_rps_p95_avgperuser_min.png")

print(f"Plots generated in: {OUT}")