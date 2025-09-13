import os
import time
import logging
from typing import Dict, Tuple, Optional
import ssl
import certifi

# Configurar certificados SSL para macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context

import fitz  # PyMuPDF
from PIL import Image, ImageFilter
import cv2
import numpy as np
import easyocr
from io import BytesIO
from openai import OpenAI
import openai


class DocumentAnalyzer:
    """Servicio para procesar documentos con OCR y analizarlos con OpenAI GPT."""

    def __init__(self) -> None:
        self.ocr_reader = None
        self.openai_client = None
        self.logger = logging.getLogger("document_analyzer")

    def initialize(self, openai_api_key: str | None, gpu: Optional[bool] = None) -> Dict:
        detalles: Dict = {"pasos_completados": []}

        # Inicializar OCR (preferir GPU si no se especifica)
        if gpu is None:
            # Intentar GPU y caer a CPU
            try:
                self.ocr_reader = easyocr.Reader(['es', 'en'], gpu=True)
                detalles["pasos_completados"].append("✅ EasyOCR inicializado (GPU)")
                self.logger.info("EasyOCR inicializado (gpu=True)")
            except Exception as e_gpu:
                self.logger.warning("Fallo inicializando EasyOCR con GPU, intentando CPU: %s", e_gpu)
                try:
                    self.ocr_reader = easyocr.Reader(['es', 'en'], gpu=False)
                    detalles["pasos_completados"].append("✅ EasyOCR inicializado (CPU)")
                    self.logger.info("EasyOCR inicializado (gpu=False)")
                except Exception as e_cpu:
                    self.ocr_reader = None
                    detalles["error_ocr"] = str(e_cpu)
                    self.logger.exception("Error inicializando EasyOCR en CPU: %s", e_cpu)
        else:
            try:
                self.ocr_reader = easyocr.Reader(['es', 'en'], gpu=gpu)
                detalles["pasos_completados"].append("✅ EasyOCR inicializado")
                self.logger.info("EasyOCR inicializado (gpu=%s)", gpu)
            except Exception as e:
                self.ocr_reader = None
                detalles["error_ocr"] = str(e)
                self.logger.exception("Error inicializando EasyOCR: %s", e)

        # Inicializar OpenAI
        if openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=openai_api_key)
                detalles["pasos_completados"].append("✅ Cliente OpenAI inicializado")
                self.logger.info("Cliente OpenAI inicializado")
            except Exception as e:
                self.openai_client = None
                detalles["error_openai"] = str(e)
                self.logger.exception("Error inicializando OpenAI: %s", e)
        else:
            detalles["advertencia_openai"] = "OPENAI_API_KEY no configurada"
            self.logger.warning("OPENAI_API_KEY no configurada")

        return detalles

    @property
    def is_ocr_ready(self) -> bool:
        return self.ocr_reader is not None

    @property
    def is_gpt_ready(self) -> bool:
        return self.openai_client is not None

    def _file_to_image(self, file_bytes: bytes, filename: str, content_type: str, request_id: Optional[str] = None) -> Tuple[Image.Image, Dict]:
        detalles: Dict = {}
        if (content_type == 'application/pdf') or filename.lower().endswith('.pdf'):
            doc = None
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if doc.page_count < 1:
                    raise ValueError("El PDF no contiene páginas")
                page = doc[0]
                zoom = 4
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, dpi=400)
                img_bytes = pix.tobytes("png")
                img = Image.open(BytesIO(img_bytes)).convert("RGB")
                detalles["conversion"] = "PDF->PNG 400DPI"
                self.logger.info("[%s] PDF convertido a imagen (400 DPI)", request_id)
            except Exception as e:
                self.logger.exception("[%s] Error convirtiendo PDF: %s", request_id, e)
                raise ValueError(f"PDF inválido o corrupto: {e}")
            finally:
                try:
                    if doc is not None:
                        doc.close()
                except Exception:
                    pass
        else:
            try:
                img = Image.open(BytesIO(file_bytes)).convert("RGB")
                detalles["conversion"] = "Imagen RGB"
                self.logger.info("[%s] Imagen cargada a RGB", request_id)
            except Exception as e:
                self.logger.exception("[%s] Error cargando imagen: %s", request_id, e)
                raise ValueError(f"Imagen inválida: {e}")
        return img, detalles

    def _preprocess_image(self, image: Image.Image, request_id: Optional[str] = None) -> Tuple[Image.Image, Dict]:
        pasos: Dict = {}
        img_cv = np.array(image)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        gray = cv2.medianBlur(gray, 3)

        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            25, 2
        )

        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        img_proc = Image.fromarray(thresh).filter(
            ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
        )

        pasos["preprocesamiento"] = "CLAHE -> MedianBlur -> AdaptiveThreshold -> MorphClose -> UnsharpMask"
        self.logger.info("[%s] Preprocesamiento aplicado", request_id)
        return img_proc, pasos

    def _extract_text(self, image_proc: Image.Image, request_id: Optional[str] = None) -> Tuple[str, Dict]:
        assert self.ocr_reader is not None, "OCR no inicializado"
        results = self.ocr_reader.readtext(np.array(image_proc), detail=1, paragraph=True)
        # Simplificado según script: sin filtro por confianza
        ocr_text = "\n".join([res[1] for res in results])
        detalles = {
            "elementos_detectados": len(results),
            "caracteres_extraidos": len(ocr_text),
            "umbral_confianza": None,
        }
        self.logger.info("[%s] OCR: elementos=%d, caracteres=%d", request_id, len(results), len(ocr_text))
        return ocr_text, detalles

    def _analyze_with_gpt(self, ocr_text: str, prompt: str, model: str, request_id: Optional[str] = None) -> Tuple[str, Dict]:
        assert self.openai_client is not None, "OpenAI no inicializado"

        # Prompt simplificado basado en el script proporcionado
        prompt_completo = f"""
Eres un experto en interpretación de planos y documentos oficiales.
Del siguiente texto extraído del plano, devuelve únicamente un JSON con los valores referentes a {prompt}.

Texto extraído del plano:
{ocr_text}

Solo responde con JSON plano, sin explicaciones ni etiquetas de código.
"""

        messages = [
            {"role": "system", "content": "Eres un experto en interpretación de documentos oficiales y planos técnicos."},
            {"role": "user", "content": prompt_completo}
        ]

        try:
            self.logger.info("[%s] Llamando a OpenAI (modelo=%s, prompt_len=%d, ocr_len=%d)", request_id, model, len(prompt), len(ocr_text))
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1
            )
        except Exception as e:
            self.logger.exception("[%s] Error OpenAI: %s", request_id, e)
            raise RuntimeError(f"Error al llamar a OpenAI: {e}")

        choices = getattr(response, 'choices', None) or []
        if not choices:
            raise RuntimeError("El modelo no devolvió resultados")
        analisis_gpt = choices[0].message.content if getattr(choices[0], 'message', None) else ""

        usage = getattr(response, 'usage', None)
        tokens_utilizados = 0
        if usage is not None:
            tokens_utilizados = getattr(usage, 'total_tokens', 0) if hasattr(usage, 'total_tokens') else usage.get('total_tokens', 0) if isinstance(usage, dict) else 0

        detalles = {
            "modelo": model,
            "tokens_utilizados": tokens_utilizados
        }
        self.logger.info("[%s] OpenAI OK (tokens=%d)", request_id, tokens_utilizados)
        return analisis_gpt, detalles

    def analyze_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        prompt: str,
        model: str = "gpt-4o-mini",
        request_id: Optional[str] = None
    ) -> Dict:
        inicio_tiempo = time.time()
        detalles: Dict = {"pasos_completados": []}
        detalles["request_id"] = request_id
        self.logger.info("[%s] Inicio análisis (file=%s, type=%s, size=%d)", request_id, filename, content_type, len(file_bytes))

        if not self.is_ocr_ready:
            raise RuntimeError("Servicio OCR no disponible")
        if not self.is_gpt_ready:
            raise RuntimeError("Servicio GPT no disponible")

        # 1) Archivo -> Imagen
        image, info_conv = self._file_to_image(file_bytes, filename, content_type, request_id)
        detalles.update(info_conv)
        detalles["pasos_completados"].append("✅ Archivo convertido a imagen")

        # 2) Preprocesamiento
        image_proc, info_prep = self._preprocess_image(image, request_id)
        detalles.update(info_prep)
        detalles["pasos_completados"].append("✅ Imagen preprocesada")

        # 3) OCR
        ocr_text, info_ocr = self._extract_text(image_proc, request_id)
        if not ocr_text or not ocr_text.strip():
            raise ValueError("No se pudo extraer texto del documento. Verifica calidad o formato.")
        detalles.update(info_ocr)
        detalles["pasos_completados"].append("✅ Texto extraído con OCR")

        # 4) GPT
        analisis_gpt, info_gpt = self._analyze_with_gpt(ocr_text, prompt, model, request_id)
        if not analisis_gpt or not analisis_gpt.strip():
            raise RuntimeError("La respuesta del modelo fue vacía")
        detalles.update(info_gpt)
        detalles["pasos_completados"].append("✅ Análisis completado con GPT")

        tiempo_total = time.time() - inicio_tiempo

        # Parseo seguro de JSON de la salida de GPT (si es posible)
        analisis_json = None
        try:
            import json
            analisis_json = json.loads(analisis_gpt)
        except Exception:
            analisis_json = None

        resultado = {
            "mensaje": "Documento analizado exitosamente",
            "nombre_archivo": filename,
            "tamaño_archivo": len(file_bytes),
            "tipo_contenido": content_type,
            "prompt_usuario": prompt,
            "texto_extraido": ocr_text,
            "analisis_gpt": analisis_gpt,
            "analisis_gpt_json": analisis_json,
            "tiempo_procesamiento": tiempo_total,
            "detalles_procesamiento": detalles,
        }
        self.logger.info("[%s] Fin análisis (%.2fs)", request_id, tiempo_total)
        return resultado


