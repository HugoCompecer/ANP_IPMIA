"""
Script para iniciar la API de clasificación de ANP.
Ejecuta el servidor FastAPI con configuración optimizada.
"""

import uvicorn

if __name__ == "__main__":
    print("🌿 INICIANDO API DE CLASIFICACIÓN DE ANP")
    print("=" * 50)
    print("📊 Documentación interactiva: http://localhost:8000/docs")
    print("🔗 Endpoint principal: POST http://localhost:8000/clasificar")
    print("💡 Ejemplo JSON: {\"latitud\": 20.5, \"longitud\": -97.5}")
    print("🏥 Salud de la API: http://localhost:8000/health")
    print("=" * 50)
    print("⏹️  Presiona Ctrl+C para detener la API")
    print()
    
    # Iniciar servidor
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
