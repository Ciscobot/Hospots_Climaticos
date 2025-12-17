# Hotspots_Climaticos
Proyección de Vulnerabilidad Climática en Sudamérica bajo el modelo IPSL-CM6A-LR, escenario SSP585.

Este repositorio contiene una serie de scripts en Python para el procesamiento, análisis y normalización regional de variables bioclimáticas (WorldClim v2.1), con el objetivo de identificar hotspots de cambio climático a escala subcontinental.

## Flujo de trabajo

### 1. Organización (`Organizacion.py`)

Este script se encarga de **extraer y organizar las variables bioclimáticas futuras** a partir de un raster multibanda proveniente de WorldClim (modelo IPSL-CM6A-LR, escenario SSP585, período 2021–2040).

El archivo de entrada contiene todas las variables bioclimáticas en un único raster multibanda. El script:  
- Selecciona únicamente las bandas de interés:
  - BIO1: Temperatura media anual
  - BIO5: Temperatura máxima del mes más cálido
  - BIO14: Precipitación del mes más seco
  - BIO15: Estacionalidad de la precipitación
- Extrae cada banda de forma independiente
- Exporta cada variable como un raster individual (`.tif`)
- Utiliza **lectura y escritura por bloques (streaming)** para minimizar el uso de memoria y permitir el manejo de rasters de gran tamaño

**Entrada:**  
- Raster multibanda futuro: `wc2.1_30s_bioc_IPSL-CM6A-LR_ssp585_2021-2040.tif`
 
**Salida:**  
- Rasters individuales:  
  - bio_1_fut.tif
  - bio_5_fut.tif
  - bio_14_fut.tif
  - bio_15_fut.tif

### 2. Recorte (`recorte.py`)

Este script realiza el **recorte espacial (clip)** de los rasters bioclimáticos históricos y futuros utilizando un **shapefile que define el área de estudio**.

El objetivo de este paso es limitar el dominio espacial de análisis exclusivamente a la región de interés, reduciendo el tamaño de los archivos y garantizando coherencia espacial entre todas las variables antes de los procesos de alineación y análisis.

El script:  
- Lee un shapefile que define el área de estudio
- Extrae todas sus geometrías (permitiendo múltiples polígonos)
- Aplica estas geometrías como máscara espacial sobre cada raster
- Genera nuevos rasters recortados conservando:
  - Resolución espacial original
  - Sistema de referencia de coordenadas (CRS)
  - Valores NoData del raster fuente
- Procesa tanto rasters históricos como futuros
- Guarda los resultados en una carpeta específica de rasters modificados

**Entrada:**  
- Shapefile del área de estudio: `VECTOR/Area_Estudio/Area_Estudio.shp`
- Rasters bioclimáticos históricos y futuros (WorldClim v2.1)

**Salida:**  
- Rasters recortados con el prefijo `recorte_`, por ejemplo:
  - recorte_wc2.1_30s_bio_1.tif
  - recorte_bio_1_fut.tif

### 3. Alineación espacial (`Alineacion.py`)

Este script se encarga de **validar y corregir la alineación espacial** de todos los rasters recortados, garantizando que sean plenamente comparables pixel a pixel antes de cualquier análisis climático.

Se utiliza un raster de referencia (`BIO1 histórico`) como estándar espacial, contra el cual se evalúan y corrigen el resto de las capas.

#### Validaciones realizadas

Para cada raster, el script verifica los siguientes criterios:  
- Sistema de referencia de coordenadas (CRS)
- Resolución espacial
- Origen del píxel (top-left)
- Extensión geográfica (extent)
- Dimensiones (número de filas y columnas)

Si uno o más de estos criterios no coincide con el raster de referencia, el archivo es marcado para corrección.

#### Corrección de alineación

Cuando un raster presenta discrepancias que requieren corrección, el script:  
- Reproyecta y remuestrea el raster usando `rasterio.warp.reproject`
- Ajusta resolución, origen, extensión y dimensiones al raster de referencia
- Utiliza interpolación bilinear (adecuada para variables continuas)
- Preserva valores NoData
- Genera un nuevo archivo alineado con el sufijo `_ali.tif`
- Mantiene compresión LZW y estructura en tiles para eficiencia de lectura

Este proceso se ejecuta únicamente sobre los rasters que lo requieren, evitando reprocesamientos innecesarios.

**Entrada:**  
- RASTER/modificados/recorte_*.tif
**Referencia espacial:**  
- `recorte_wc2.1_30s_bio_1.tif`
**Salida:**
`recorte_bio_x_ali.tif` (si requirió corrección)

### 4. Análisis climático (`analisis.py`)

Este script constituye el **núcleo analítico del proyecto**, donde se calculan los **cambios bioclimáticos**, su **normalización regional** y los **rasters de Z-score**, que posteriormente serán utilizados para la evaluación de hotspots de vulnerabilidad climática.

El análisis se realiza sobre capas raster previamente **recortadas y alineadas**, garantizando consistencia espacial completa.

## Etapas del análisis

### A.1 Cálculo de deltas bioclimáticos

Para cada variable bioclimática (BIO1, BIO5, BIO14, BIO15), el script calcula el cambio climático como:

`DELTA = Futuro − Histórico`

Características clave del proceso:  
- Procesamiento en **streaming por bloques** (`block_windows`) para minimizar uso de memoria
- Validación estricta de alineación (CRS, resolución, extensión y dimensiones)
- Propagación correcta de valores NoData
- **Inversión temprana del signo de BIO14** (precipitación del mes más seco), de modo que valores positivos representen mayor estrés hídrico, manteniendo coherencia semántica con el resto de las variables

Salida:
`DELTA_bio_*.tif`

### A.2 Estadísticas regionales (media y desviación estándar)

A partir de los rasters de delta, se calculan **estadísticas zonales** por región administrativa definida en el vector de área de estudio:  
- Media regional
- Desviación estándar regional

Estas estadísticas permiten capturar la **idiosincrasia climática regional**, evitando una normalización global que diluya contrastes locales.

El cálculo se realiza mediante `zonal_stats`, considerando todos los píxeles tocados por cada polígono (`all_touched=True`).

Los valores se incorporan como atributos al GeoDataFrame de regiones.

### A.3 Rasterización de medias y desviaciones

Las medias y desviaciones estándar regionales se rasterizan para cada variable bioclimática, utilizando como referencia espacial el raster BIO1 histórico.

Este paso permite:  
- Representar estadísticos regionales como capas raster
- Aplicar **álgebra de mapas continua**, sin necesidad de iterar región por región

Salidas:
`MEAN_bio_*.tif`
`STD_bio_*.tif`

Cada píxel hereda el valor estadístico correspondiente a la región en la que se encuentra.


### A.4 Normalización Z-score regional

Finalmente, se calcula la normalización Z-score para cada píxel:
`Z = (DELTA − MEDIA_regional) / STD_regional`

Características del proceso:  
- Normalización **regional**, no global
- Procesamiento en streaming
- Control explícito de NoData y desviaciones inválidas
- Generación de rasters Z-score directamente comparables entre variables

Salida:
`Z_bio_*.tif`

## Resultados del script

Al finalizar, el script genera:

- Deltas bioclimáticos por variable
- Rasters de media y desviación estándar regional
- Rasters normalizados Z-score por variable

Estos productos constituyen la base para:
- Construcción de índices compuestos
- Identificación de hotspots climáticos
- Análisis zonales y rankings de vulnerabilidad
