# Ejecución única de pruebas de disponibilidad (Windows PowerShell).
# Requisitos: Docker, uv, API de reservas en :8002 si se ejecutan escenarios G.
#
# Uso:
#   .\run_disponibilidad.ps1
#   .\run_disponibilidad.ps1 -Skip "G_capacidad,G_capacidad_sweep"
#   .\run_disponibilidad.ps1 -WithCapacidadSweep
#   .\run_disponibilidad.ps1 -NoDockerE1E2 -NoIdsCompose
#   .\run_disponibilidad.ps1 -WithRegisters

param(
    [string] $Skip = "",
    [switch] $WithCapacidadSweep,
    [switch] $WithRegisters,
    [switch] $NoDockerE1E2,
    [switch] $NoIdsCompose,
    [switch] $NoSeedIds
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

if (-not $NoIdsCompose) {
    Write-Host "Levantando PostgreSQL IDS (docker-compose.ids.yml)..."
    docker compose -f "$RepoRoot\docker-compose.ids.yml" up -d
    Start-Sleep -Seconds 3
    if (-not $NoSeedIds) {
        $schema = Join-Path $RepoRoot "scripts\ids_postgres_schema.sql"
        $seed = Join-Path $RepoRoot "scripts\ids_postgres_seed.sql"
        if ((Test-Path $schema) -and (Test-Path $seed)) {
            Write-Host "Sembrando IDS (schema + seed)..."
            Get-Content $schema -Raw | docker exec -i ids_postgres psql -U postgres -d postgres 2>$null
            Get-Content $seed -Raw | docker exec -i ids_postgres psql -U postgres -d postgres 2>$null
        }
    }
}

if ($WithRegisters) {
    $regCompose = Join-Path $RepoRoot "registers\docker-compose.yml"
    if (Test-Path $regCompose) {
        Write-Host "Levantando stack registers (reservations_service en :8002)..."
        docker compose -f $regCompose up -d
        Start-Sleep -Seconds 5
    } else {
        Write-Warning "No se encontró registers\docker-compose.yml; omitiendo -WithRegisters."
    }
}

$argsList = @("-m", "scripts.disponibilidad.run_all", "--start-api")
if ($Skip -ne "") {
    $argsList += @("--skip", $Skip)
}
if ($WithCapacidadSweep) {
    $argsList += "--with-capacidad-sweep"
}
if ($NoDockerE1E2) {
    $argsList += "--no-docker-e1e2"
}

Write-Host "Ejecutando orquestador: $($argsList -join ' ')"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv run python @argsList
} else {
    $env:PYTHONPATH = $RepoRoot
    python @argsList
}

Write-Host "Listo. Revise registers\data\test\results\resumen_global.csv"
