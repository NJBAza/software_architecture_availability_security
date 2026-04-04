import math
from datetime import datetime, timezone
import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import Json
from fastapi import APIRouter, HTTPException, Depends

router = APIRouter()

# DB_CONFIG = {
#     "dbname": "postgres",
#     "user": "postgres",
#     "password": "1234",
#     "host": "localhost",
#     "port": "5432",
# }
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "ids_db"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", "root"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "options": "-c search_path=public"
}

UMBRAL_RIESGO = 75.0
MAX_VELOCIDAD_HUMANA_KMH = 900.0  

# 1. Inicializar el Pool de Conexiones (Min: 1, Max: 20 conexiones simultáneas)
try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(1, 20, **DB_CONFIG)
except Exception as e:
    print(f"Error fatal al inicializar el pool de conexiones: {e}")
    raise e

# 2. Crear la dependencia de FastAPI para gestionar el ciclo de vida de la conexión
def obtener_conexion():
    """Obtiene una conexión del pool y la devuelve al terminar la petición."""
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        # Esto se ejecuta SIEMPRE al final de la petición HTTP, devolviendo la conexión al pool
        db_pool.putconn(conn)


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # ... (Misma lógica anterior)
    R = 6371.0 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def obtener_linea_base_usuario(cursor, id_usuario: int):
    query = """
        SELECT 
            p.latitud, p.longitud, p.inicio_sesion, p.promedio_pxm,
            array_agg(d.dispositivo) FILTER (WHERE d.confiable = TRUE) as dispositivos_confiables
        FROM perfile_seguridad_usuario p
        LEFT JOIN dispositivo_usuario d ON p.id_usuario = d.id_usuario
        WHERE p.id_usuario = %s
        GROUP BY p.id_usuario;
    """
    cursor.execute(query, (id_usuario,))
    return cursor.fetchone()

def registrar_incidente(cursor, id_usuario: int, riesgo: float, anomalias: list, ip: str):
    query_incidente = """
        INSERT INTO incidente (id_usuario, riesgo, anomalia, ip)
        VALUES (%s, %s, %s, %s);
    """
    cursor.execute(query_incidente, (id_usuario, riesgo, Json(anomalias), ip))
    query_bloqueo = "UPDATE usuario SET estado = 'BLOQUEADO' WHERE id = %s;"
    cursor.execute(query_bloqueo, (id_usuario,))

# 3. Inyectar la conexión usando Depends(obtener_conexion)
@router.get("/api/v1/ids/detectar/{id_usuario}")
def detectar_intrusion(
    id_usuario: int, 
    latitud_actual: float, 
    longitud_actual: float, 
    dispositivo_actual: str, 
    tasa_peticiones_actual: float,
    ip_actual: str,
    conn = Depends(obtener_conexion) # <-- Magia de FastAPI aquí
):
    puntaje_riesgo = 0.0
    anomalias = []
    
    # Ya no abrimos la conexión aquí, usamos la inyectada
    cursor = conn.cursor()

    try:
        baseline = obtener_linea_base_usuario(cursor, id_usuario)
        if not baseline:
            raise HTTPException(status_code=404, detail="Perfil de usuario no encontrado")

        lat_hist, lon_hist, inicio_sesion, promedio_pxm, dispositivos_conocidos = baseline
        
        lat_hist = float(lat_hist)
        lon_hist = float(lon_hist)
        promedio_pxm = float(promedio_pxm) if promedio_pxm else 0.0

        if dispositivos_conocidos is None: dispositivos_conocidos = []
        
        # Evaluar Geo-Velocity
        horas_transcurridas = (datetime.now(timezone.utc) - inicio_sesion).total_seconds() / 3600.0
        if horas_transcurridas > 0:
            distancia_km = calcular_distancia_haversine(lat_hist, lon_hist, latitud_actual, longitud_actual)
            velocidad = distancia_km / horas_transcurridas
            if velocidad > MAX_VELOCIDAD_HUMANA_KMH:
                puntaje_riesgo += 50.0
                anomalias.append(f"geo_velocidad_imposible_kmh_{velocidad:.0f}")

        # Evaluar Device Fingerprint
        if dispositivo_actual not in dispositivos_conocidos:
            puntaje_riesgo += 30.0
            anomalias.append("dispositivo_desconocido")

        # Evaluar Behavioral Patterns
        if promedio_pxm > 0 and tasa_peticiones_actual > (float(promedio_pxm) * 3):
            puntaje_riesgo += 20.0
            anomalias.append("tasa_peticiones_inusual")

        es_fraude = puntaje_riesgo >= UMBRAL_RIESGO

        if es_fraude:
            registrar_incidente(cursor, id_usuario, puntaje_riesgo, anomalias, ip_actual)
            conn.commit()

        return {
            "id_usuario": id_usuario,
            "riesgo": puntaje_riesgo,
            "es_incidente_fraude": es_fraude,
            "anomalias": anomalias
        }

    except Exception as e:
        conn.rollback() # Revertimos cambios si algo falla
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()