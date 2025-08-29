# 🌿 Clasificador de Áreas Naturales Protegidas (ANP)

Sistema para determinar si una coordenada geográfica está dentro de un área natural protegida en México y clasificar según los criterios de MIA (Manifestación de Impacto Ambiental).

## 📋 Características

- ✅ **Detección de ANP**: Verifica si una coordenada está dentro de un área natural protegida
- ✅ **Análisis de colindancia**: Detecta si la coordenada está ≤ 500m de límites estatales
- ✅ **Clasificación MIA**: Clasifica automáticamente entre MIA regional, MIA particular o IP
- ✅ **Observaciones especiales**: Identifica cercanía a ANPs de alto valor ecológico
- ✅ **Datos actualizados**: Utiliza shapefile oficial con 232 ANPs de México

## 🚀 Instalación

1. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

2. **Verificar estructura de archivos:**
```
IPMIA/
├── anp_classifier.py          # Script principal
├── requirements.txt          # Dependencias
├── README.md                 # Documentación
├── shape_files/
│   └── areas_naturales_protegidas/
│       ├── 232_ANP-ITRF08_04072025.shp
│       ├── 232_ANP-ITRF08_04072025.dbf
│       ├── 232_ANP-ITRF08_04072025.shx
│       └── 232_ANP-ITRF08_04072025.prj
└── mexico-geojson/
    └── 2023/
        └── states/
            ├── Aguascalientes.json
            ├── Baja California.json
            └── ... (todos los estados)
```

## 📖 Uso Básico

### Ejemplo Simple

```python
from anp_classifier import ANPClassifier

# Inicializar clasificador
classifier = ANPClassifier()

# Cargar datos
classifier.load_anp_data()
classifier.load_states_data()

# Analizar coordenada
latitud = 20.5
longitud = -97.5
resultado = classifier.classify_coordinate(latitud, longitud)

print(f"Clasificación MIA: {resultado['clasificacionMIA']}")
print(f"En ANP: {resultado['anp']['pertenece']}")
print(f"Colinda entre estados: {resultado['colindaEntreEstados']}")
```

### Ejecutar Script Principal

```bash
python anp_classifier.py
```



## 🎯 Criterios de Clasificación

### Clasificación MIA (Prioridad Estricta)

1. **MIA Regional** → Si `colindaEntreEstados: true` (incluso si también está dentro de un ANP)
2. **MIA Particular** → Si `anp.pertenece: true` y no aplica la condición anterior
3. **IP** → Si no aplica ninguna de las anteriores

### Colindancia entre Estados

- `colindaEntreEstados: true` → Si la coordenada está ≤ 500m de un límite estatal
- `colindaEntreEstados: false` → Si está claramente dentro de un solo estado

### Observaciones Especiales

Si está a < 2 km de un ANP de alto valor ecológico (RAMSAR, UNESCO, Reserva de la Biosfera, etc.):
> "Cercanía a [nombre del ANP], categoría [tipo], reconocido internacionalmente. SEMARNAT podría solicitar MIA por impacto indirecto."

## 📊 Estructura del Resultado

```json
{
  "coordenadas": {
    "latitud": 20.5,
    "longitud": -97.5
  },
  "anp": {
    "pertenece": false
  },
  "colindaEntreEstados": true,
  "clasificacionMIA": "MIA regional",
  "justificacion": "La coordenada se encuentra ≤ 500 m de un límite estatal",
  "observaciones": [
    "No se identifican observaciones ambientales relevantes."
  ]
}
```

## 🏞️ Categorías de ANP Reconocidas

- **APFF**: Área de Protección de Flora y Fauna
- **APRN**: Área de Protección de Recursos Naturales  
- **PN**: Parque Nacional
- **RB**: Reserva de la Biosfera
- **MN**: Monumento Natural
- **SANT**: Santuario

## 🌍 Datos Utilizados

- **ANPs**: Shapefile oficial con 232 áreas naturales protegidas (ITRF08)
- **Estados**: GeoJSON de los 32 estados mexicanos (2023)
- **Proyección**: WGS84 (EPSG:4326) para entrada, UTM Zona 14N para cálculos de distancia

## ⚙️ Funciones Principales

### `ANPClassifier.classify_coordinate(lat, lon)`
Función principal que realiza toda la clasificación.

### `ANPClassifier.check_point_in_anp(lat, lon)`
Verifica si un punto está dentro de un ANP.

### `ANPClassifier.check_state_boundary_proximity(lat, lon)`
Verifica cercanía a límites estatales (≤ 500m).

### `ANPClassifier.check_high_value_anp_proximity(lat, lon)`
Identifica ANPs de alto valor ecológico cercanas (< 2km).

## 🔧 Requisitos del Sistema

- Python 3.8+
- GeoPandas 0.13.0+
- Pandas 1.5.0+
- Shapely 2.0.0+

## 📝 Ejemplos de Coordenadas

```python
# Ejemplos para probar
coordenadas = [
    {"lat": 19.4326, "lon": -99.1332},  # Ciudad de México
    {"lat": 21.1619, "lon": -86.8515},  # Cancún
    {"lat": 20.6597, "lon": -103.3496}, # Guadalajara
    {"lat": 25.6866, "lon": -100.3161}  # Monterrey
]
```

## 🐛 Solución de Problemas

1. **Error al cargar shapefile**: Verificar que todos los archivos (.shp, .dbf, .shx, .prj) estén presentes
2. **Error al cargar estados**: Verificar que la carpeta `mexico-geojson/2023/states/` contenga todos los archivos JSON
3. **Error de dependencias**: Ejecutar `pip install -r requirements.txt`

## 📧 Soporte

Para reportar problemas o sugerencias, verificar:
- Que las coordenadas estén en formato decimal (WGS84)
- Que la latitud esté entre 14.5 y 32.7 (límites de México)
- Que la longitud esté entre -118.4 y -86.7 (límites de México)

---

**Desarrollado para análisis ambiental y clasificación MIA en México** 🇲🇽
