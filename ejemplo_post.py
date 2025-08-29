"""
Ejemplo simple de cómo usar la API de clasificación de ANP con método POST.
Muestra diferentes formas de enviar coordenadas en formato JSON.
"""

import requests
import json

# URL base de la API
API_URL = "http://localhost:8000"

def clasificar_coordenada(latitud, longitud):
    """
    Clasifica una coordenada usando la API POST.
    
    Args:
        latitud (float): Latitud en grados decimales
        longitud (float): Longitud en grados decimales
    
    Returns:
        dict: Resultado de la clasificación o None si hay error
    """
    
    # Preparar datos JSON
    datos = {
        "latitud": latitud,
        "longitud": longitud
    }
    
    try:
        # Realizar petición POST
        response = requests.post(
            f"{API_URL}/clasificar",
            json=datos,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar a la API.")
        print("💡 Asegúrate de que esté ejecutándose con: python iniciar_api.py")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def ejemplo_basico():
    """Ejemplo básico de clasificación."""
    
    print("🎯 EJEMPLO BÁSICO - CLASIFICACIÓN DE COORDENADA")
    print("-" * 50)
    
    # Coordenada de ejemplo
    latitud = 20.5
    longitud = -97.5
    
    print(f"📍 Clasificando coordenada: {latitud}, {longitud}")
    
    resultado = clasificar_coordenada(latitud, longitud)
    
    if resultado:
        print("\n✅ RESULTADO:")
        print(f"🏞️  En ANP: {'Sí' if resultado['anp']['pertenece'] else 'No'}")
        
        if resultado['anp']['pertenece']:
            print(f"   📍 ANP: {resultado['anp']['nombre']}")
            print(f"   🏷️  Categoría: {resultado['anp']['categoria']}")
        
        print(f"🗺️  Colinda entre estados: {'Sí' if resultado['colindaEntreEstados'] else 'No'}")
        print(f"📋 Clasificación MIA: {resultado['clasificacionMIA']}")
        print(f"💡 Justificación: {resultado['justificacion']}")
        
        if resultado['observaciones']:
            print("\n📝 Observaciones:")
            for obs in resultado['observaciones']:
                print(f"   • {obs}")

def ejemplo_multiple():
    """Ejemplo con múltiples coordenadas."""
    
    print("\n\n🎯 EJEMPLO MÚLTIPLE - VARIAS COORDENADAS")
    print("-" * 50)
    
    coordenadas = [
        {"lat": 19.4326, "lon": -99.1332, "nombre": "Ciudad de México"},
        {"lat": 21.1619, "lon": -86.8515, "nombre": "Cancún, Q.R."},
        {"lat": 20.6597, "lon": -103.3496, "nombre": "Guadalajara, JAL"},
        {"lat": 25.6866, "lon": -100.3161, "nombre": "Monterrey, N.L."}
    ]
    
    for coord in coordenadas:
        print(f"\n🔍 Analizando: {coord['nombre']}")
        print(f"   Coordenadas: {coord['lat']}, {coord['lon']}")
        
        resultado = clasificar_coordenada(coord['lat'], coord['lon'])
        
        if resultado:
            clasificacion = resultado['clasificacionMIA']
            en_anp = "Sí" if resultado['anp']['pertenece'] else "No"
            colinda = "Sí" if resultado['colindaEntreEstados'] else "No"
            
            print(f"   📋 MIA: {clasificacion}")
            print(f"   🏞️  ANP: {en_anp}")
            print(f"   🗺️  Colinda: {colinda}")
        else:
            print("   ❌ Error en clasificación")

def ejemplo_con_curl():
    """Mostrar ejemplos equivalentes con curl."""
    
    print("\n\n🎯 EJEMPLOS EQUIVALENTES CON CURL")
    print("-" * 50)
    
    ejemplos_curl = [
        {
            "descripcion": "Clasificar coordenada básica",
            "comando": """curl -X POST "http://localhost:8000/clasificar" \\
     -H "Content-Type: application/json" \\
     -d '{"latitud": 20.5, "longitud": -97.5}'"""
        },
        {
            "descripcion": "Con formato bonito (jq)",
            "comando": """curl -X POST "http://localhost:8000/clasificar" \\
     -H "Content-Type: application/json" \\
     -d '{"latitud": 19.4326, "longitud": -99.1332}' | jq"""
        },
        {
            "descripcion": "Desde archivo JSON",
            "comando": """echo '{"latitud": 21.1619, "longitud": -86.8515}' > coord.json
curl -X POST "http://localhost:8000/clasificar" \\
     -H "Content-Type: application/json" \\
     -d @coord.json"""
        }
    ]
    
    for ejemplo in ejemplos_curl:
        print(f"\n📝 {ejemplo['descripcion']}:")
        print(f"```bash")
        print(f"{ejemplo['comando']}")
        print(f"```")

def ejemplo_validacion():
    """Ejemplo de validación de coordenadas."""
    
    print("\n\n🎯 EJEMPLO DE VALIDACIÓN")
    print("-" * 50)
    
    # Coordenadas inválidas para probar validación
    coordenadas_invalidas = [
        {"lat": 50.0, "lon": -100.0, "error": "Latitud fuera de rango para México"},
        {"lat": 20.0, "lon": -200.0, "error": "Longitud fuera de rango para México"},
        {"lat": 10.0, "lon": -97.0, "error": "Latitud muy al sur para México"}
    ]
    
    for coord in coordenadas_invalidas:
        print(f"\n🧪 Probando coordenada inválida: {coord['lat']}, {coord['lon']}")
        print(f"   Razón: {coord['error']}")
        
        resultado = clasificar_coordenada(coord['lat'], coord['lon'])
        if resultado is None:
            print("   ✅ Validación funcionando correctamente")
        else:
            print("   ⚠️  La validación no funcionó como esperado")

if __name__ == "__main__":
    print("🌿 EJEMPLOS DE USO - API POST CLASIFICACIÓN DE ANP")
    print("=" * 60)
    
    # Verificar que la API esté disponible
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API disponible")
        else:
            print("⚠️  API responde pero con errores")
    except:
        print("❌ API no disponible. Ejecuta: python iniciar_api.py")
        print("\n⏹️  Saliendo...")
        exit(1)
    
    # Ejecutar ejemplos
    ejemplo_basico()
    ejemplo_multiple()
    ejemplo_con_curl()
    ejemplo_validacion()
    
    print("\n" + "=" * 60)
    print("🎉 ¡Ejemplos completados!")
    print("📖 Más información: http://localhost:8000/docs")
    print("=" * 60)
