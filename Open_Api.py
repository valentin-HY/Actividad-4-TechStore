"""Guarda el contrato OpenAPI de la API en openapi.json"""
import json
from app.api import app

with open("openapi.json", "w", encoding="utf-8") as f:
    json.dump(app.openapi(), f, ensure_ascii=False, indent=2)
print("openapi.json generado")