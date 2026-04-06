# Deteccion con 1 condicion individual

Prueba cada una de las 3 condiciones del IDS por separado:
- **geo** (+50): geo-velocity imposible — riesgo 50, NO fraude
- **dispositivo** (+30): dispositivo desconocido — riesgo 30, NO fraude
- **tasa** (+20): tasa de peticiones anomala — riesgo 20, NO fraude

Ninguna condicion individual alcanza el umbral de 75 para fraude.

Niveles: 10, 100, 1000, 10000, 20000, 100000 solicitudes por condicion.

## Resultados
- `results/resumen.csv` — condicion, nivel, deteccion_correcta_pct, falsos_positivos, avg_ms
- `results/detalle.csv` — id_usuario, condicion, es_fraude_obtenido, riesgo, duracion_ms
