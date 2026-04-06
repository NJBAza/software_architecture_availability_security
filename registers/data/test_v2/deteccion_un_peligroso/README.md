# Deteccion de un usuario peligroso

Crea 1 usuario peligroso (geo-velocity + dispositivo desconocido = riesgo 80 >= 75) y verifica que el IDS lo detecta en menos de 300ms.

## Resultados
- `results/detalle.csv` — id_usuario, es_fraude_obtenido, riesgo, duracion_ms, en_menos_300ms
