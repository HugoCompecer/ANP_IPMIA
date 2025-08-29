"""
Script de prueba para la API de clasificación de ANP.
Realiza peticiones HTTP para verificar que todos los endpoints funcionan correctamente.
"""

import requests
import json
import time

# Configuración
BASE_URL = "http://localhost:8000"

def test_api():
    """Ejecutar todas las pruebas de la API."""
    
    print("🧪 PRUEBAS DE LA API DE CLASIFICACIÓN DE ANP")
    print("=" * 60)
    
    # Esperar un poco para que la API arranque
    print("⏳ Esperando que la API esté lista...")
    time.sleep(2)
    
    # 1. Probar endpoint raíz
    try:
        print("\n1️⃣ Probando endpoint raíz...")
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Endpoint raíz funcionando")
            data = response.json()
            print(f"   Mensaje: {data.get('mensaje', 'N/A')}")
        else:
            print(f"❌ Error en endpoint raíz: {response.status_code}")
    except Exception as e:
        print(f"❌ Error conectando a la API: {e}")
        print("💡 Asegúrate de que la API esté ejecutándose con: python iniciar_api.py")
        return
    
    # 2. Probar estado de salud
    try:
        print("\n2️⃣ Probando estado de salud...")
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API saludable")
            data = response.json()
            print(f"   ANPs cargadas: {data.get('anp_cargadas', 'N/A')}")
            print(f"   Estados cargados: {data.get('estados_cargados', 'N/A')}")
        else:
            print(f"❌ Problema de salud: {response.status_code}")
    except Exception as e:
        print(f"❌ Error en health check: {e}")
    
    # 3. Probar clasificación de coordenadas
    coordenadas_prueba = [
        {"lat": 20.5, "lon": -97.5, "desc": "Coordenada que colinda entre estados"},
        {"lat": 19.4326, "lon": -99.1332, "desc": "Ciudad de México"},
        {"lat": 21.1619, "lon": -86.8515, "desc": "Cancún"}
    ]
    
    for i, coord in enumerate(coordenadas_prueba, 3):
        try:
            print(f"\n{i}️⃣ Probando clasificación - {coord['desc']}...")
            json_data = {
                "latitud": coord["lat"],
                "longitud": coord["lon"]
            }
            response = requests.post(
                f"{BASE_URL}/clasificar",
                json=json_data
            )
            
            if response.status_code == 200:
                print("✅ Clasificación exitosa")
                data = response.json()
                print(f"   Clasificación MIA: {data.get('clasificacionMIA', 'N/A')}")
                print(f"   En ANP: {data.get('anp', {}).get('pertenece', 'N/A')}")
                print(f"   Colinda entre estados: {data.get('colindaEntreEstados', 'N/A')}")
            else:
                print(f"❌ Error en clasificación: {response.status_code}")
                print(f"   Detalle: {response.text}")
        except Exception as e:
            print(f"❌ Error en clasificación: {e}")
    
    # 4. Probar listado de categorías
    try:
        print("\n6️⃣ Probando listado de categorías...")
        response = requests.get(f"{BASE_URL}/categorias")
        if response.status_code == 200:
            print("✅ Categorías obtenidas")
            data = response.json()
            print(f"   Total categorías: {data.get('total_categorias', 'N/A')}")
            categorias = data.get('categorias', [])
            if categorias:
                print(f"   Primera categoría: {categorias[0].get('codigo', 'N/A')} - {categorias[0].get('descripcion', 'N/A')}")
        else:
            print(f"❌ Error obteniendo categorías: {response.status_code}")
    except Exception as e:
        print(f"❌ Error obteniendo categorías: {e}")
    
    # 5. Probar listado de ANPs
    try:
        print("\n7️⃣ Probando listado de ANPs...")
        response = requests.get(f"{BASE_URL}/anp/lista", params={"limite": 3})
        if response.status_code == 200:
            print("✅ ANPs obtenidas")
            data = response.json()
            print(f"   Total disponibles: {data.get('total_disponibles', 'N/A')}")
            print(f"   Filtradas: {data.get('filtradas', 'N/A')}")
            anps = data.get('anps', [])
            if anps:
                print(f"   Primera ANP: {anps[0].get('nombre', 'N/A')}")
        else:
            print(f"❌ Error obteniendo ANPs: {response.status_code}")
    except Exception as e:
        print(f"❌ Error obteniendo ANPs: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 Pruebas completadas!")
    print("📊 Para ver documentación interactiva: http://localhost:8000/docs")

def ejemplo_uso_python():
    """Ejemplo de cómo usar la API desde Python."""
    
    print("\n🐍 EJEMPLO DE USO DESDE PYTHON")
    print("-" * 40)
    
    # Coordenada de ejemplo
    lat, lon = 20.5, -97.5
    
    try:
        # Preparar datos JSON
        json_data = {
            "latitud": lat,
            "longitud": lon
        }
        
        # Realizar petición POST
        response = requests.post(
            f"{BASE_URL}/clasificar",
            json=json_data,
            timeout=10
        )
        
        if response.status_code == 200:
            resultado = response.json()
            
            print(f"📍 Coordenadas: {lat}, {lon}")
            print(f"🏞️  En ANP: {'Sí' if resultado['anp']['pertenece'] else 'No'}")
            
            if resultado['anp']['pertenece']:
                print(f"   ANP: {resultado['anp']['nombre']}")
                print(f"   Categoría: {resultado['anp']['categoria']}")
            
            print(f"🗺️  Colinda entre estados: {'Sí' if resultado['colindaEntreEstados'] else 'No'}")
            print(f"📋 Clasificación MIA: {resultado['clasificacionMIA']}")
            print(f"💡 Justificación: {resultado['justificacion']}")
            
            if resultado['observaciones']:
                print("📝 Observaciones:")
                for obs in resultado['observaciones']:
                    print(f"   • {obs}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar a la API.")
        print("💡 Asegúrate de que esté ejecutándose con: python iniciar_api.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Ejecutar pruebas
    test_api()
    
    # Mostrar ejemplo de uso
    ejemplo_uso_python()
    
    print("\n📚 Más información en: http://localhost:8000/docs")
