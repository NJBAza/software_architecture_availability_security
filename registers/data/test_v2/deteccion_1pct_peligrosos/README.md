# Deteccion 1% peligrosos a escala

Genera N usuarios donde el 1% son peligrosos (geo+dispositivo = 80 >= 75) y el 99% son normales. Envia solicitudes al IDS para todos y mide precision y velocidad de deteccion.

Niveles: 10, 100, 1000, 10000, 20000, 100000 usuarios.

## Resultados
- `results/resumen.csv` — nivel, deteccion_correcta_pct, en_menos_300ms_pct, latencias
- `results/detalle.csv` — id_usuario, tipo_usuario, es_fraude_obtenido, riesgo, duracion_ms
