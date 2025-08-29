"""
Script para determinar si una coordenada está dentro de un área natural protegida (ANP)
y clasificar según los criterios de MIA (Manifestación de Impacto Ambiental).

Autor: Sistema de clasificación ambiental
Fecha: 2025
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union
import json
import os
from typing import Dict, List, Tuple, Optional
import warnings

# Suprimir warnings de deprecación
warnings.filterwarnings('ignore')

class ANPClassifier:
    """Clasificador de áreas naturales protegidas y análisis de colindancia."""
    
    def __init__(self):
        """Inicializar el clasificador cargando los datos necesarios."""
        self.anp_gdf = None
        self.states_gdf = None
        self.high_value_anp_categories = {
            'RB',  # Reserva de la Biosfera
            'PN',  # Parque Nacional
            'MN'   # Monumento Natural
        }
        self.international_keywords = [
            'RAMSAR', 'UNESCO', 'BIOSFERA', 'PATRIMONIO', 'MUNDIAL',
            'INTERNATIONAL', 'BIOSPHERE', 'HERITAGE'
        ]
        
    def load_anp_data(self, shapefile_path: str = None):
        """Cargar datos de áreas naturales protegidas."""
        if shapefile_path is None:
            shapefile_path = r"shape_files\areas_naturales_protegidas\232_ANP-ITRF08_04072025.shp"
        
        try:
            self.anp_gdf = gpd.read_file(shapefile_path)
            print(f"✓ Cargadas {len(self.anp_gdf)} áreas naturales protegidas")
            return True
        except Exception as e:
            print(f"✗ Error cargando ANP: {e}")
            return False
    
    def load_states_data(self, states_dir: str = None):
        """Cargar datos de estados mexicanos."""
        if states_dir is None:
            states_dir = r"mexico-geojson\2023\states"
        
        try:
            state_files = [f for f in os.listdir(states_dir) if f.endswith('.json')]
            gdfs = []
            
            for state_file in state_files:
                state_path = os.path.join(states_dir, state_file)
                state_name = state_file.replace('.json', '')
                
                with open(state_path, 'r', encoding='utf-8') as f:
                    geojson_data = json.load(f)
                
                state_gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
                state_gdf['estado'] = state_name
                gdfs.append(state_gdf)
            
            self.states_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
            self.states_gdf = self.states_gdf.set_crs("EPSG:4326")
            print(f"✓ Cargados {len(state_files)} estados mexicanos")
            return True
        except Exception as e:
            print(f"✗ Error cargando estados: {e}")
            return False
    
    def get_state_boundaries_buffer(self, buffer_meters: float = 500):
        """Crear buffer de límites estatales."""
        if self.states_gdf is None:
            return None
        
        # Proyectar a UTM para mediciones en metros (zona 14N para México)
        states_utm = self.states_gdf.to_crs("EPSG:32614")
        
        # Crear unión de todos los estados
        all_states_union = unary_union(states_utm.geometry)
        
        # Obtener límites (bordes) de los estados
        boundaries = all_states_union.boundary
        
        # Crear buffer de 500 metros
        buffer_area = boundaries.buffer(buffer_meters)
        
        # Convertir de vuelta a WGS84
        buffer_gdf = gpd.GeoDataFrame([1], geometry=[buffer_area], crs="EPSG:32614")
        buffer_gdf = buffer_gdf.to_crs("EPSG:4326")
        
        return buffer_gdf
    
    def check_point_in_anp(self, lat: float, lon: float) -> Dict:
        """Verificar si un punto está dentro de un ANP."""
        if self.anp_gdf is None:
            return {"error": "Datos de ANP no cargados"}
        
        point = Point(lon, lat)
        point_gdf = gpd.GeoDataFrame([1], geometry=[point], crs="EPSG:4326")
        
        # Verificar intersección con ANPs
        intersections = gpd.sjoin(point_gdf, self.anp_gdf, how="inner", predicate="intersects")
        
        if len(intersections) > 0:
            anp_info = self.anp_gdf.iloc[intersections.index_right.iloc[0]]
            return {
                "pertenece": True,
                "nombre": anp_info['NOMBRE'],
                "categoria": anp_info['CAT_MANEJO'],
                "estados": anp_info['ESTADOS'],
                "region": anp_info['REGION'],
                "superficie": anp_info['SUPERFICIE'],
                "fecha_decreto": anp_info['PRIM_DEC'].strftime('%Y-%m-%d') if pd.notna(anp_info['PRIM_DEC']) else None
            }
        else:
            return {"pertenece": False}
    
    def check_state_boundary_proximity(self, lat: float, lon: float, buffer_meters: float = 500) -> bool:
        """Verificar si un punto está cerca de límites estatales."""
        if self.states_gdf is None:
            return False
        
        point = Point(lon, lat)
        
        # Proyectar punto a UTM
        point_gdf = gpd.GeoDataFrame([1], geometry=[point], crs="EPSG:4326")
        point_utm = point_gdf.to_crs("EPSG:32614")
        
        # Proyectar estados a UTM
        states_utm = self.states_gdf.to_crs("EPSG:32614")
        
        # Verificar en cuántos estados está el punto (con buffer)
        point_buffered = point_utm.geometry.iloc[0].buffer(buffer_meters)
        
        intersecting_states = states_utm[states_utm.geometry.intersects(point_buffered)]
        
        return len(intersecting_states) > 1
    
    def check_high_value_anp_proximity(self, lat: float, lon: float, distance_km: float = 2.0) -> List[Dict]:
        """Verificar cercanía a ANPs de alto valor ecológico."""
        if self.anp_gdf is None:
            return []
        
        point = Point(lon, lat)
        point_gdf = gpd.GeoDataFrame([1], geometry=[point], crs="EPSG:4326")
        point_utm = point_gdf.to_crs("EPSG:32614")
        
        # Proyectar ANPs a UTM
        anp_utm = self.anp_gdf.to_crs("EPSG:32614")
        
        # Crear buffer de 2 km alrededor del punto
        buffer_area = point_utm.geometry.iloc[0].buffer(distance_km * 1000)
        
        # Encontrar ANPs dentro del buffer
        nearby_anps = anp_utm[anp_utm.geometry.intersects(buffer_area)]
        
        high_value_anps = []
        for idx, anp in nearby_anps.iterrows():
            is_high_value = False
            recognition_type = []
            
            # Verificar categoría de manejo
            if anp['CAT_MANEJO'] in self.high_value_anp_categories:
                is_high_value = True
                recognition_type.append(f"Categoría {anp['CAT_MANEJO']}")
            
            # Verificar palabras clave internacionales en el nombre
            nombre_upper = anp['NOMBRE'].upper()
            for keyword in self.international_keywords:
                if keyword in nombre_upper:
                    is_high_value = True
                    recognition_type.append(f"Reconocimiento {keyword}")
            
            # Verificar certificación SINAP
            if pd.notna(anp['CERT_SINAP']):
                is_high_value = True
                recognition_type.append(f"Certificación {anp['CERT_SINAP']}")
            
            if is_high_value:
                high_value_anps.append({
                    "nombre": anp['NOMBRE'],
                    "categoria": anp['CAT_MANEJO'],
                    "reconocimiento": ", ".join(recognition_type),
                    "distancia_aproximada": "< 2 km"
                })
        
        return high_value_anps
    
    def classify_coordinate(self, lat: float, lon: float) -> Dict:
        """Clasificar una coordenada según los criterios MIA."""
        if self.anp_gdf is None or self.states_gdf is None:
            return {"error": "Datos no cargados correctamente"}
        
        # Verificar si está en ANP
        anp_result = self.check_point_in_anp(lat, lon)
        
        # Verificar colindancia entre estados
        colinda_estados = self.check_state_boundary_proximity(lat, lon)
        
        # Verificar cercanía a ANPs de alto valor
        nearby_high_value = self.check_high_value_anp_proximity(lat, lon)
        
        # Clasificación MIA según prioridad estricta
        if colinda_estados:
            mia_classification = "MIA regional"
            justificacion = "La coordenada se encuentra ≤ 500 m de un límite estatal"
        elif anp_result.get("pertenece", False):
            mia_classification = "MIA particular"
            justificacion = f"La coordenada está dentro del ANP: {anp_result['nombre']}"
        else:
            mia_classification = "IP"
            justificacion = "La coordenada no está en ANP ni cerca de límites estatales"
        
        # Generar observaciones
        observaciones = []
        
        if nearby_high_value:
            for anp in nearby_high_value:
                obs = f"Cercanía a {anp['nombre']}, categoría {anp['categoria']}"
                if anp['reconocimiento']:
                    obs += f", {anp['reconocimiento']}"
                obs += ". SEMARNAT podría solicitar MIA por impacto indirecto."
                observaciones.append(obs)
        
        if not observaciones and not anp_result.get("pertenece", False):
            observaciones.append("No se identifican observaciones ambientales relevantes.")
        
        # Estructura del resultado
        resultado = {
            "coordenadas": {
                "latitud": lat,
                "longitud": lon
            },
            "anp": anp_result,
            "colindaEntreEstados": colinda_estados,
            "clasificacionMIA": mia_classification,
            "justificacion": justificacion,
            "observaciones": observaciones
        }
        
        return resultado

def main():
    """Función principal para demostrar el uso del clasificador."""
    print("=== CLASIFICADOR DE ÁREAS NATURALES PROTEGIDAS ===\n")
    
    # Inicializar clasificador
    classifier = ANPClassifier()
    
    # Cargar datos
    print("Cargando datos...")
    if not classifier.load_anp_data():
        print("Error: No se pudieron cargar los datos de ANP")
        return
    
    if not classifier.load_states_data():
        print("Error: No se pudieron cargar los datos de estados")
        return
    
    print("\n✓ Datos cargados correctamente\n")
    
    # Ejemplo de uso
    print("=== EJEMPLO DE CLASIFICACIÓN ===")
    
    # Coordenada de ejemplo (puedes cambiar estos valores)
    lat_ejemplo = 31.604914
    lon_ejemplo = -106.459206






    print(f"Analizando coordenada: {lat_ejemplo}, {lon_ejemplo}")
    print("-" * 50)
    
    resultado = classifier.classify_coordinate(lat_ejemplo, lon_ejemplo)
    
    # Mostrar resultados
    print(f"📍 Coordenadas: {resultado['coordenadas']['latitud']}, {resultado['coordenadas']['longitud']}")
    print(f"🏞️  En ANP: {'Sí' if resultado['anp']['pertenece'] else 'No'}")
    
    if resultado['anp']['pertenece']:
        print(f"   - Nombre: {resultado['anp']['nombre']}")
        print(f"   - Categoría: {resultado['anp']['categoria']}")
        print(f"   - Estados: {resultado['anp']['estados']}")
    
    print(f"🗺️  Colinda entre estados: {'Sí' if resultado['colindaEntreEstados'] else 'No'}")
    print(f"📋 Clasificación MIA: {resultado['clasificacionMIA']}")
    print(f"💡 Justificación: {resultado['justificacion']}")
    
    print("\n📝 Observaciones:")
    for obs in resultado['observaciones']:
        print(f"   • {obs}")
    
    print("\n" + "="*60)
    print("Para usar con otras coordenadas, llama a:")
    print("resultado = classifier.classify_coordinate(latitud, longitud)")

if __name__ == "__main__":
    main()
