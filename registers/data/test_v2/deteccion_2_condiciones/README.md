# Deteccion con 2 condiciones combinadas

Prueba las 3 combinaciones posibles de pares de condiciones:
- **geo+dispositivo** (50+30=80): SI fraude (>= 75)
- **geo+tasa** (50+20=70): NO fraude (< 75)
- **dispositivo+tasa** (30+20=50): NO fraude (< 75)

Niveles: 10, 100, 1000, 10000, 20000, 100000 solicitudes por combinacion.

## Resultados
- `results/resumen.csv` — combo, nivel, fraude_esperado, deteccion_correcta_pct, en_menos_300ms_pct
- `results/detalle.csv` — id_usuario, combo, es_fraude_obtenido, riesgo, duracion_ms
