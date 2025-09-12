"""
API REST para el clasificador de Áreas Naturales Protegidas (ANP).
Endpoint para determinar si una coordenada está en ANP y clasificar según criterios MIA.

Autor: Sistema de clasificación ambiental
Fecha: 2025
"""

from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import uvicorn
import pandas as pd
import os
import fitz  # PyMuPDF
from PIL import Image, ImageFilter
import cv2
import numpy as np
import easyocr
from io import BytesIO
from openai import OpenAI
import json
import time
from anp_classifier import ANPClassifier

# Variables globales para el clasificador
classifier = None
openai_client = None
ocr_reader = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""
    global classifier, openai_client, ocr_reader
    
    # Startup: Cargar datos del clasificador
    print("🌿 Iniciando API de Clasificación de ANP...")
    print("📂 Cargando datos...")
    
    classifier = ANPClassifier()
    
    if not classifier.load_anp_data():
        raise Exception("❌ Error: No se pudieron cargar los datos de ANP")
    
    if not classifier.load_states_data():
        raise Exception("❌ Error: No se pudieron cargar los datos de estados")
    
    print("✅ Datos de ANP cargados correctamente")
    
    # Inicializar cliente OpenAI (solo si hay API key)
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = OpenAI(api_key=openai_api_key)
        print("✅ Cliente OpenAI inicializado")
    else:
        print("⚠️  Variable OPENAI_API_KEY no encontrada - funciones OCR+GPT deshabilitadas")
    
    # Inicializar EasyOCR
    try:
        print("📖 Inicializando EasyOCR...")
        ocr_reader = easyocr.Reader(['es', 'en'], gpu=False)  # GPU=False para compatibilidad
        print("✅ EasyOCR inicializado")
    except Exception as e:
        print(f"⚠️  Error inicializando EasyOCR: {str(e)} - funciones OCR deshabilitadas")
    
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

class ArchivoResponse(BaseModel):
    mensaje: str = Field(..., description="Mensaje de confirmación")
    nombre_archivo: str = Field(..., description="Nombre del archivo subido")
    tamaño_archivo: int = Field(..., description="Tamaño del archivo en bytes")
    tipo_contenido: Optional[str] = Field(None, description="Tipo MIME del archivo")
    texto_enviado: str = Field(..., description="String enviado junto con el archivo")
    ruta_guardado: Optional[str] = Field(None, description="Ruta donde se guardó el archivo")

class OCRAnalisisResponse(BaseModel):
    mensaje: str = Field(..., description="Mensaje de confirmación del procesamiento")
    nombre_archivo: str = Field(..., description="Nombre del archivo procesado")
    tamaño_archivo: int = Field(..., description="Tamaño del archivo en bytes")
    tipo_contenido: Optional[str] = Field(None, description="Tipo MIME del archivo")
    prompt_usuario: str = Field(..., description="Prompt/consulta del usuario")
    texto_extraido: str = Field(..., description="Texto completo extraído por OCR")
    analisis_gpt: Optional[str] = Field(None, description="Análisis estructurado por GPT-4o-mini")
    tiempo_procesamiento: float = Field(..., description="Tiempo total de procesamiento en segundos")
    detalles_procesamiento: Dict = Field(..., description="Detalles del procesamiento realizado")

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
            "subir-archivo": "POST /subir-archivo (Form: archivo + texto)",
            "analizar-documento": "POST /analizar-documento (Form: archivo + prompt)",
            "anp/lista": "GET /anp/lista (filtrar ANPs)",
            "categorias": "GET /categorias (categorías de ANP)",
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

@app.post("/subir-archivo",
          response_model=ArchivoResponse,
          summary="Subir archivo con texto",
          description="Endpoint para subir un archivo junto con un string de texto",
          responses={
              200: {"description": "Archivo subido exitosamente"},
              400: {"model": ErrorResponse, "description": "Error en los parámetros enviados"},
              413: {"model": ErrorResponse, "description": "Archivo demasiado grande"},
              500: {"model": ErrorResponse, "description": "Error interno del servidor"}
          })
async def subir_archivo_con_texto(
    archivo: UploadFile = File(..., description="Archivo a subir"),
    texto: str = Form(..., description="Texto o string a enviar junto con el archivo"),
    guardar_archivo: bool = Form(False, description="Si debe guardarse el archivo en el servidor")
):
    """
    Endpoint para subir un archivo junto con un string de texto.
    
    ## Parámetros:
    - **archivo**: Archivo a subir (cualquier tipo)
    - **texto**: String o texto a enviar junto con el archivo
    - **guardar_archivo**: Opcional, indica si el archivo debe guardarse en el servidor (default: False)
    
    ## Restricciones:
    - Tamaño máximo de archivo: 50MB
    - Tipos de archivo permitidos: Todos
    
    ## Respuesta:
    - Información del archivo subido
    - El texto enviado
    - Ruta de guardado (si se especificó guardar_archivo=True)
    
    ## Ejemplo de uso:
    ```bash
    curl -X POST "http://localhost:8000/subir-archivo" \\
         -F "archivo=@mi_archivo.txt" \\
         -F "texto=Mi texto personalizado" \\
         -F "guardar_archivo=true"
    ```
    """
    
    try:
        # Verificar tamaño del archivo (50MB máximo)
        max_size = 50 * 1024 * 1024  # 50MB en bytes
        
        # Leer el contenido del archivo para obtener su tamaño
        contenido = await archivo.read()
        tamaño_archivo = len(contenido)
        
        if tamaño_archivo > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Archivo demasiado grande. Tamaño máximo: 50MB. Tamaño actual: {tamaño_archivo / 1024 / 1024:.2f}MB"
            )
        
        ruta_guardado = None
        
        # Si se especifica guardar el archivo
        if guardar_archivo:
            # Crear directorio de uploads si no existe
            directorio_uploads = "uploads"
            if not os.path.exists(directorio_uploads):
                os.makedirs(directorio_uploads)
            
            # Generar nombre único para evitar sobrescribir
            import time
            timestamp = str(int(time.time()))
            nombre_unico = f"{timestamp}_{archivo.filename}"
            ruta_guardado = os.path.join(directorio_uploads, nombre_unico)
            
            # Guardar el archivo
            with open(ruta_guardado, "wb") as f:
                f.write(contenido)
        
        # Preparar respuesta
        respuesta = ArchivoResponse(
            mensaje="Archivo procesado exitosamente",
            nombre_archivo=archivo.filename,
            tamaño_archivo=tamaño_archivo,
            tipo_contenido=archivo.content_type,
            texto_enviado=texto,
            ruta_guardado=ruta_guardado
        )
        
        return respuesta
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando archivo: {str(e)}"
        )

@app.post("/analizar-documento",
          response_model=OCRAnalisisResponse,
          summary="Analizar documento con OCR + GPT",
          description="Extrae texto de documentos (PDF/imágenes) y analiza el contenido usando GPT-4o-mini",
          responses={
              200: {"description": "Análisis completado exitosamente"},
              400: {"model": ErrorResponse, "description": "Error en los parámetros enviados"},
              413: {"model": ErrorResponse, "description": "Archivo demasiado grande"},
              503: {"model": ErrorResponse, "description": "Servicios OCR/GPT no disponibles"},
              500: {"model": ErrorResponse, "description": "Error interno del servidor"}
          })
async def analizar_documento_ocr_gpt(
    archivo: UploadFile = File(..., description="Documento a analizar (PDF, JPG, JPEG, PNG)"),
    prompt: str = Form(..., description="Consulta o datos específicos que quieres encontrar en el documento"),
    modelo_gpt: str = Form("gpt-4o-mini", description="Modelo GPT a usar (gpt-4o-mini, gpt-4o)")
):
    """
    Analiza documentos usando OCR avanzado y GPT para extraer información específica.
    
    ## Proceso:
    1. **Carga del documento**: Acepta PDF, JPG, JPEG, PNG
    2. **Procesamiento de imagen**: Mejora la calidad para OCR óptimo
    3. **Extracción OCR**: Usa EasyOCR con preprocesamiento avanzado
    4. **Análisis GPT**: Interpreta el texto según tu consulta específica
    
    ## Parámetros:
    - **archivo**: Documento a procesar (PDF se convierte a imagen de alta resolución)
    - **prompt**: Consulta específica (ej: "coordenadas y dimensiones del terreno")
    - **modelo_gpt**: Modelo OpenAI a usar (default: gpt-4o-mini)
    
    ## Tipos de archivo soportados:
    - **PDF**: Se renderiza la primera página a 400 DPI
    - **JPG/JPEG/PNG**: Se procesan directamente
    
    ## Restricciones:
    - Tamaño máximo: 50MB
    - Requiere variables de entorno: OPENAI_API_KEY
    
    ## Ejemplo de uso:
    ```bash
    curl -X POST "http://localhost:8000/analizar-documento" \\
         -F "archivo=@plano_arquitectonico.pdf" \\
         -F "prompt=Extrae las coordenadas UTM y dimensiones del terreno"
    ```
    """
    
    inicio_tiempo = time.time()
    detalles = {"pasos_completados": []}
    
    try:
        # Verificaciones iniciales
        if ocr_reader is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio OCR no disponible. EasyOCR no se pudo inicializar."
            )
        
        if openai_client is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio GPT no disponible. Configure la variable OPENAI_API_KEY."
            )
        
        # Verificar tipo de archivo
        tipos_soportados = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
        if archivo.content_type not in tipos_soportados and not archivo.filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de archivo no soportado. Use: PDF, JPG, JPEG, PNG"
            )
        
        # Leer archivo
        contenido = await archivo.read()
        tamaño_archivo = len(contenido)
        
        # Verificar tamaño (50MB máximo)
        max_size = 50 * 1024 * 1024
        if tamaño_archivo > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Archivo demasiado grande. Máximo: 50MB. Actual: {tamaño_archivo / 1024 / 1024:.2f}MB"
            )
        
        detalles["pasos_completados"].append("✅ Archivo cargado y validado")
        
        # 🔄 PASO 1: Procesamiento del archivo a imagen
        if archivo.content_type == 'application/pdf' or archivo.filename.lower().endswith('.pdf'):
            # Procesar PDF
            doc = fitz.open(stream=contenido, filetype="pdf")
            page = doc[0]  # Primera página
            zoom = 4  # Resolución muy alta
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, dpi=400)
            img_bytes = pix.tobytes("png")
            img = Image.open(BytesIO(img_bytes)).convert("RGB")
            doc.close()
            detalles["pasos_completados"].append("✅ PDF convertido a imagen de alta resolución (400 DPI)")
        else:
            # Procesar imagen
            img = Image.open(BytesIO(contenido)).convert("RGB")
            detalles["pasos_completados"].append("✅ Imagen cargada y convertida a RGB")
        
        # 🔄 PASO 2: Preprocesamiento avanzado con OpenCV
        img_cv = np.array(img)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
        
        # Mejorar contraste local con CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # Aplicar filtro de mediana para reducir ruido
        gray = cv2.medianBlur(gray, 3)
        
        # Binarización adaptativa más precisa
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            25, 2
        )
        
        # Morfología para mejorar trazos de caracteres
        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Filtro de nitidez con PIL
        img_proc = Image.fromarray(thresh).filter(
            ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
        )
        
        detalles["pasos_completados"].append("✅ Imagen preprocesada con OpenCV (CLAHE, filtros, binarización)")
        
        # 🔄 PASO 3: OCR con EasyOCR
        results = ocr_reader.readtext(np.array(img_proc), detail=1, paragraph=True)
        ocr_text = "\n".join([res[1] for res in results if res[2] > 0.5])  # Solo confianza > 50%
        
        if not ocr_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer texto del documento. Verifica la calidad de la imagen."
            )
        
        detalles["pasos_completados"].append(f"✅ Texto extraído con EasyOCR ({len(results)} elementos detectados)")
        detalles["caracteres_extraidos"] = len(ocr_text)
        
        # 🔄 PASO 4: Análisis con GPT
        prompt_completo = f"""
Eres un experto en interpretación de planos y documentos oficiales.
Del siguiente texto extraído del documento, devuelve únicamente un JSON con los valores referentes a: {prompt}

Texto extraído del documento:
{ocr_text}

Instrucciones:
- Solo responde con JSON válido, sin explicaciones ni etiquetas de código
- Si no encuentras la información solicitada, indica "no_encontrado": true
- Estructura la respuesta de forma clara y organizada
- Incluye unidades de medida cuando aplique
"""
        
        messages = [
            {"role": "system", "content": "Eres un experto en interpretación de documentos oficiales y planos técnicos."},
            {"role": "user", "content": prompt_completo}
        ]
        
        response = openai_client.chat.completions.create(
            model=modelo_gpt,
            messages=messages,
            temperature=0.1  # Respuestas más precisas y consistentes
        )
        
        analisis_gpt = response.choices[0].message.content
        detalles["pasos_completados"].append(f"✅ Análisis completado con {modelo_gpt}")
        detalles["tokens_utilizados"] = response.usage.total_tokens if hasattr(response, 'usage') else 0
        
        # Calcular tiempo total
        tiempo_total = time.time() - inicio_tiempo
        
        # Preparar respuesta
        return OCRAnalisisResponse(
            mensaje="Documento analizado exitosamente",
            nombre_archivo=archivo.filename,
            tamaño_archivo=tamaño_archivo,
            tipo_contenido=archivo.content_type,
            prompt_usuario=prompt,
            texto_extraido=ocr_text,
            analisis_gpt=analisis_gpt,
            tiempo_procesamiento=tiempo_total,
            detalles_procesamiento=detalles
        )
        
    except HTTPException:
        raise
    except Exception as e:
        tiempo_error = time.time() - inicio_tiempo
        detalles["error_en_paso"] = len(detalles["pasos_completados"])
        detalles["tiempo_hasta_error"] = tiempo_error
        
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando documento: {str(e)}"
        )

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
