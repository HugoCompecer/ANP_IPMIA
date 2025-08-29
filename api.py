"""
API REST para el clasificador de Áreas Naturales Protegidas (ANP).
Endpoint para determinar si una coordenada está en ANP y clasificar según criterios MIA.

Autor: Sistema de clasificación ambiental
Fecha: 2025
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import uvicorn
import pandas as pd
from anp_classifier import ANPClassifier

# Variables globales para el clasificador
classifier = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""
    global classifier
    
    # Startup: Cargar datos del clasificador
    print("🌿 Iniciando API de Clasificación de ANP...")
    print("📂 Cargando datos...")
    
    classifier = ANPClassifier()
    
    if not classifier.load_anp_data():
        raise Exception("❌ Error: No se pudieron cargar los datos de ANP")
    
    if not classifier.load_states_data():
        raise Exception("❌ Error: No se pudieron cargar los datos de estados")
    
    print("✅ Datos cargados correctamente")
    print("🚀 API lista para recibir peticiones")
    
    yield
    
    # Shutdown
    print("🔚 Cerrando API...")

# Crear aplicación FastAPI
app = FastAPI(
    title="API Clasificador de Áreas Naturales Protegidas",
    description="""
    API para determinar si una coordenada geográfica está dentro de un área natural protegida 
    en México y clasificar según los criterios de MIA (Manifestación de Impacto Ambiental).
    
    ## Características:
    - ✅ Detección de ANP
    - ✅ Análisis de colindancia entre estados (≤ 500m)
    - ✅ Clasificación MIA automática (Regional/Particular/IP)
    - ✅ Observaciones para ANPs de alto valor ecológico
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de request y respuesta
class CoordenadasRequest(BaseModel):
    latitud: float = Field(..., ge=14.5, le=32.7, description="Latitud de la coordenada (14.5° a 32.7° N para México)", example=20.5)
    longitud: float = Field(..., ge=-118.4, le=-86.7, description="Longitud de la coordenada (-118.4° a -86.7° O para México)", example=-97.5)

class CoordenadasModel(BaseModel):
    latitud: float = Field(..., description="Latitud de la coordenada")
    longitud: float = Field(..., description="Longitud de la coordenada")

class ANPModel(BaseModel):
    pertenece: bool = Field(..., description="Si la coordenada está dentro de un ANP")
    nombre: Optional[str] = Field(None, description="Nombre del ANP (si aplica)")
    categoria: Optional[str] = Field(None, description="Categoría de manejo del ANP")
    estados: Optional[str] = Field(None, description="Estados donde se ubica el ANP")
    region: Optional[str] = Field(None, description="Región del ANP")
    superficie: Optional[float] = Field(None, description="Superficie del ANP en hectáreas")
    fecha_decreto: Optional[str] = Field(None, description="Fecha de decreto del ANP")

class ClasificacionResponse(BaseModel):
    coordenadas: CoordenadasModel
    anp: ANPModel
    colindaEntreEstados: bool = Field(..., description="Si está ≤ 500m de límites estatales")
    clasificacionMIA: str = Field(..., description="Clasificación MIA: Regional/Particular/IP")
    justificacion: str = Field(..., description="Justificación de la clasificación")
    observaciones: List[str] = Field(..., description="Observaciones adicionales")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Descripción del error")
    detalle: Optional[str] = Field(None, description="Detalles adicionales del error")

# Endpoints
@app.get("/", 
         summary="Información de la API",
         description="Endpoint de información básica de la API")
async def root():
    """Endpoint raíz con información de la API."""
    return {
        "mensaje": "🌿 API Clasificador de Áreas Naturales Protegidas",
        "version": "1.0.0",
        "descripcion": "API para clasificación MIA según ubicación en ANPs",
        "endpoints": {
            "clasificar": "POST /clasificar (JSON: {latitud, longitud})",
            "docs": "/docs",
            "salud": "/health"
        }
    }

@app.get("/health",
         summary="Estado de salud de la API",
         description="Verificar que la API y los datos estén funcionando correctamente")
async def health_check():
    """Endpoint para verificar el estado de salud de la API."""
    if classifier is None:
        raise HTTPException(status_code=503, detail="Clasificador no inicializado")
    
    return {
        "estado": "saludable",
        "clasificador": "activo",
        "anp_cargadas": len(classifier.anp_gdf) if classifier.anp_gdf is not None else 0,
        "estados_cargados": len(classifier.states_gdf.estado.unique()) if classifier.states_gdf is not None else 0
    }

@app.post("/clasificar",
          response_model=ClasificacionResponse,
          summary="Clasificar coordenada",
          description="Clasifica una coordenada según criterios MIA y verifica si está en ANP",
          responses={
              200: {"description": "Clasificación exitosa"},
              400: {"model": ErrorResponse, "description": "Parámetros inválidos"},
              422: {"description": "Error de validación de datos"},
              500: {"model": ErrorResponse, "description": "Error interno del servidor"}
          })
async def clasificar_coordenada(coordenadas: CoordenadasRequest):
    """
    Clasifica una coordenada geográfica según los criterios de MIA.
    
    ## Request Body (JSON):
    ```json
    {
        "latitud": 20.5,
        "longitud": -97.5
    }
    ```
    
    ## Parámetros:
    - **latitud**: Latitud en grados decimales (WGS84) - Rango: 14.5° a 32.7° N
    - **longitud**: Longitud en grados decimales (WGS84) - Rango: -118.4° a -86.7° O
    
    ## Clasificación MIA:
    1. **MIA Regional**: Si está ≤ 500m de límites estatales
    2. **MIA Particular**: Si está en ANP sin colindancia estatal
    3. **IP**: Si no aplica ninguna anterior
    
    ## Observaciones:
    - Se generan alertas para ANPs de alto valor ecológico cercanas (< 2km)
    - Incluye información detallada del ANP si la coordenada está dentro
    """
    
    try:
        # Verificar que el clasificador esté inicializado
        if classifier is None:
            raise HTTPException(
                status_code=503, 
                detail="Clasificador no disponible. Contacte al administrador."
            )
        
        # Realizar clasificación
        resultado = classifier.classify_coordinate(coordenadas.latitud, coordenadas.longitud)
        
        # Verificar si hay errores en el resultado
        if "error" in resultado:
            raise HTTPException(
                status_code=500,
                detail=f"Error en clasificación: {resultado['error']}"
            )
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor: {str(e)}"
        )

@app.get("/anp/lista",
         summary="Listar ANPs",
         description="Obtener lista de todas las áreas naturales protegidas disponibles")
async def listar_anps(
    limite: int = Query(10, ge=1, le=100, description="Número máximo de ANPs a mostrar"),
    categoria: Optional[str] = Query(None, description="Filtrar por categoría (APFF, RB, PN, etc.)")
):
    """Obtener lista de ANPs disponibles con filtros opcionales."""
    
    try:
        if classifier is None or classifier.anp_gdf is None:
            raise HTTPException(status_code=503, detail="Datos de ANP no disponibles")
        
        # Aplicar filtro de categoría si se especifica
        anps = classifier.anp_gdf.copy()
        if categoria:
            anps = anps[anps['CAT_MANEJO'].str.upper() == categoria.upper()]
        
        # Limitar resultados
        anps = anps.head(limite)
        
        # Formatear respuesta
        lista_anps = []
        for idx, anp in anps.iterrows():
            lista_anps.append({
                "id": anp['NUM_ANP'],
                "nombre": anp['NOMBRE'],
                "categoria": anp['CAT_MANEJO'],
                "estados": anp['ESTADOS'],
                "superficie": anp['SUPERFICIE'],
                "fecha_decreto": anp['PRIM_DEC'].strftime('%Y-%m-%d') if pd.notna(anp['PRIM_DEC']) else None
            })
        
        return {
            "total_disponibles": len(classifier.anp_gdf),
            "filtradas": len(anps),
            "anps": lista_anps
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo ANPs: {str(e)}")

@app.get("/categorias",
         summary="Obtener categorías de ANP",
         description="Lista las categorías de manejo disponibles para las ANPs")
async def obtener_categorias():
    """Obtener lista de categorías de manejo de ANPs."""
    
    try:
        if classifier is None or classifier.anp_gdf is None:
            raise HTTPException(status_code=503, detail="Datos de ANP no disponibles")
        
        categorias = classifier.anp_gdf['CAT_MANEJO'].unique().tolist()
        categorias_info = {
            'APFF': 'Área de Protección de Flora y Fauna',
            'APRN': 'Área de Protección de Recursos Naturales',
            'PN': 'Parque Nacional', 
            'RB': 'Reserva de la Biosfera',
            'MN': 'Monumento Natural',
            'SANT': 'Santuario'
        }
        
        resultado = []
        for cat in sorted(categorias):
            resultado.append({
                "codigo": cat,
                "descripcion": categorias_info.get(cat, "Descripción no disponible"),
                "cantidad": len(classifier.anp_gdf[classifier.anp_gdf['CAT_MANEJO'] == cat])
            })
        
        return {
            "categorias": resultado,
            "total_categorias": len(categorias)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo categorías: {str(e)}")

# Función para ejecutar la API
def run_api():
    """Ejecutar la API en modo desarrollo."""
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    print("🌿 Iniciando API de Clasificación de ANP...")
    print("📊 Documentación disponible en: http://localhost:8000/docs")
    print("🔗 Endpoint principal: http://localhost:8000/clasificar?latitud=20.5&longitud=-97.5")
    run_api()
