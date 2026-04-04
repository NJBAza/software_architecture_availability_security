# ids_service/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Importamos el router que contiene la lógica de detección
from app.services import IDS

app = FastAPI(
    title="IDS Service (Anomaly Detector)",
    description="Microservicio encargado de evaluar el comportamiento de los usuarios y detectar intrusiones en tiempo real.",
    version="1.0.0",
    docs_url=None, 
    redoc_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(IDS.router)

@app.get("/health", tags=["System"])
def health_check():
    """Verifica que el servicio esté arriba."""
    return {"status": "ok", "service": "ids_service"}

@app.get("/scalar", response_class=HTMLResponse, include_in_schema=False)
def scalar_html():
    """Genera la interfaz de documentación con Scalar."""
    return f"""
    <!DOCTYPE html>
    <html>
      <head>
        <title>IDS Service API Reference</title>
        <meta charset="utf-8" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1" />
        <style>
          body {{
            margin: 0;
          }}
        </style>
      </head>
      <body>
        <script
          id="api-reference"
          data-url="/openapi.json"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    """