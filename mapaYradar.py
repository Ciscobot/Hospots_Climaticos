import matplotlib.pyplot as plt
import geopandas as gpd
import xarray as xr
import rioxarray as rx
import numpy as np
from matplotlib.ticker import MultipleLocator

import pandas as pd
from matplotlib.gridspec import GridSpec
from math import pi
import matplotlib.pyplot as plt




# 1. CONFIGURACION DE RUTAS
ruta_raster = "/home/victor/Documentos/Trabajos_Investigacion/Proyección_Hotspots/RESULTADOS/INDICE_IMPACTO_AGREGADO.tif"

ruta_vector = "/home/victor/Documentos/Trabajos_Investigacion/Proyección_Hotspots/VECTOR/Area_Estudio/Area_Estudio.shp"

# 2. CARGA Y PREPARACION DEL RASTER
try:
    # masked=True convierte el -9999.0 en NaN 
    raster = rx.open_rasterio(ruta_raster, masked=True)
    
    if len(raster.shape) > 2:
        raster = raster.isel(band=0)

    # Calculo de cuantiles para la escala, aca se ignora NaNs para no arruinar la escala con valores extremos
    #vmin, vmax = np.nanpercentile(raster.values, [5, 95])
    # Podemos tambien definir nuestra escala personalizada con valor minimo y maximo
    vmin, vmax = -2, 2

except Exception as e:
    print(f"Error cargando raster: {e}")
    exit()

# 3. CARGA Y RECORTE DEL SHP
try:
    provincias = gpd.read_file(ruta_vector).to_crs(raster.rio.crs)
    # RECORTE:
    # .cx[longitud, latitud] me permite recortar el shp 
    # Cortamos Antartida de nuestro Vector
    provincias_continentales = provincias.cx[:, -56.2:0]

except Exception as e:
    print(f"Error cargando vector: {e}")
    provincias_continentales = None

# 4. GENERACION DEL MAPA
fig, ax = plt.subplots(figsize=(10, 10), facecolor='white') # tamaño del visor(plot) en pulgadas(ancho,alto)

im = raster.plot(
    ax=ax,
    cmap='RdYlGn_r', # Rojo = riesgo ALTO, Verde = riesgo BAJO
    vmin=vmin,
    vmax=vmax,
    add_colorbar=True,
    cbar_kwargs={
        'label': 'Índice de Impacto (Z-score)',
        'shrink': 0.7,
        'pad': 0.02
    }
)

cbar = im.colorbar
cbar.set_ticks([-2, -1, 0, 1, 2]) # valores de la barra de la escala

# Graficar Lineas del Vector recortado encima del raster
if provincias_continentales is not None:
    provincias_continentales.plot(
        ax=ax, 
        facecolor="none", 
        edgecolor="#333333", 
        linewidth=0.7, 
        alpha=0.8
    )

# 5. VISUALIZACION Y AJUSTES DE DISEÑO

ax.set_ylim(-56.5, -17.0)  # de Tierra del Fuego al norte de Paraguay/Brasil
ax.set_xlim(-76.0, -45.0)  # de la Cordillera de los Andes a Uruguay

# Detalles etiquetas y titulo
ax.set_title("Áreas críticas de Vulnerabilidade à Mudança climática na América do Sul", fontsize=15, pad=20) 
ax.set_xlabel("Longitude", fontsize=10)
ax.set_ylabel("Latitude", fontsize=10) 
# cada cuantos grados va una linea
ax.xaxis.set_major_locator(MultipleLocator(10)) 
ax.yaxis.set_major_locator(MultipleLocator(15)) 
ax.grid(True, linestyle='--', alpha=0.2) 

# visualizar sin ajuste de margenes:
#plt.tight_layout() 
#plt.show()

# visualizar con ajuste de margenes:
fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1) # valores se expresan en porcentaje de 0.0 a 1.0
plt.show()

# 6. RADARES Y PLOTS
ruta_excel = "/home/victor/Documentos/Trabajos_Investigacion/Proyección_Hotspots/RESULTADOS/Reporte_Hotspots_Zonal_MultiPais.xlsx"

df = pd.read_excel(ruta_excel, sheet_name="Ranking Global de Riesgo")

categorias_z = ['z_bio1', 'z_bio5', 'z_bio14', 'z_bio15']
nombres_eje = ['BIO1', 'BIO5', 'BIO14 (Sequía)', 'BIO15']

cores_top = ['#e41a1c', '#ff7f00', '#984ea3', '#a65628', '#377eb8']
cores_bottom = ['#4daf4a', '#377eb8', '#a65628', '#984ea3', '#ff7f00']


def radares_fig(ax, df_top, df_bottom, titulo):
    
    angles = [n / float(len(categorias_z)) * 2 * pi for n in range(len(categorias_z))]
    angles += angles[:1]

    max_val = max(
        df_top[categorias_z].abs().max().max(),
        df_bottom[categorias_z].abs().max().max()
    ) * 1.2

    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(nombres_eje, fontsize=9)
    ax.set_rlim(-max_val, max_val)
    ax.set_title(titulo, fontsize=12, pad=18)

    # TOP MAYOR RIESGO
    for i, (_, row) in enumerate(df_top.iterrows()):
        values = row[categorias_z].tolist()
        values += values[:1]
        ax.plot(
            angles,
            values,
            linewidth=1.5,
            color=cores_top[i % len(cores_top)],
            label=f"{row['NOMBRE_ZONA']} (Alto)" )
        ax.fill(
            angles,
            values,
            alpha=0.10,
            color=cores_top[i % len(cores_top)])

    # TOP MENOR RIESGO
    for i, (_, row) in enumerate(df_bottom.iterrows()):
        values = row[categorias_z].tolist()
        values += values[:1]

        ax.plot(
            angles,
            values,
            linewidth=1,
            linestyle='--',
            color=cores_bottom[i % len(cores_bottom)],
            label=f"{row['NOMBRE_ZONA']} (Bajo)")
        ax.fill(
            angles,
            values,
            alpha=0.10,
            color=cores_bottom[i % len(cores_bottom)])

    # LEYENDA DE RADAR A LA DERECHA
    ax.legend(
        loc='center left',
        bbox_to_anchor=(1.25, 0.5),
        fontsize=8,
        frameon=False)


fig = plt.figure(figsize=(20, 11))
gs = GridSpec(3, 2, figure=fig, height_ratios=[1, 1, 1.35])

paises = ['PARAGUAY', 'URUGUAY', 'BRASIL', 'ARGENTINA']
posiciones = [(0, 0), (0, 1), (1, 0), (1, 1)]

# RADARES POR PAIS

for pais, (i, j) in zip(paises, posiciones):
    df_pais = (
        df[df['PAIS_KEY'] == pais]
        .sort_values('Indice_consolidado', ascending=False)
        .copy())

    if len(df_pais) < 3:
        continue

    top = df_pais.head(3)
    bottom = df_pais.tail(3).sort_values('Indice_consolidado')

    ax = fig.add_subplot(gs[i, j], polar=True)

    radares_fig(
        ax=ax,
        df_top=top,
        df_bottom=bottom,
        titulo=f"{pais} – Top 3 Mayor / Menor Riesgo")

# RADAR GLOBAL

df_global = df.sort_values('Indice_consolidado', ascending=False)

top_global = df_global.head(5)
bottom_global = df_global.tail(5).sort_values('Indice_consolidado')

ax_global = fig.add_subplot(gs[2, :], polar=True)

radares_fig(
    ax=ax_global,
    df_top=top_global,
    df_bottom=bottom_global,
    titulo="Sudamérica – Top 5 Mayor / Menor Riesgo Climático")

plt.tight_layout()
plt.show()