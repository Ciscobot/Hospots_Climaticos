from math import pi
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rioxarray as rx
from matplotlib.colors import BoundaryNorm
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MultipleLocator


# ===================================================
# CONFIGURACIÓN GENERAL
# ===================================================

BASE_DIR = Path("./RASTER")
VECTOR_DIR = Path("./VECTOR")
TABLES_DIR = Path("./TABLES")

IC_PATH = BASE_DIR.joinpath("derivados", "Indice_Consolidado.tif")
VECTOR_PATH = VECTOR_DIR.joinpath("Area_Estudio", "Area_Estudio.shp")
EXCEL_PATH = TABLES_DIR.joinpath("Reporte_Hotspots_Area_Estudio.xlsx")

FIGURE_DIR = Path("./GRAFICOS/")
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

MAP_OUTPUT_CUARTILES = FIGURE_DIR.joinpath("Mapa_Indice_Consolidado.png")
MAP_OUTPUT_PERCENTILES = FIGURE_DIR.joinpath(
    "Mapa_Indice_Consolidado_percentiles.png"
)
RADAR_OUTPUT = FIGURE_DIR.joinpath("Mapa_Radares_Riesgo.png")

# ===================================================
# VALIDACIÓN DE ARCHIVOS
# ===================================================

for path in [IC_PATH, VECTOR_PATH, EXCEL_PATH]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo requerido: {path}")


# ===================================================
# FUNCIÓN MAPA
# ===================================================


def crear_mapa_indice(
    raster_path,
    vector_path,
    output_path,
    modo_color="percentiles",
):
    """
    Genera y guarda mapa del índice consolidado.

    modo_color:
        - "percentiles" → escala continua (p10–p90)
        - "cuartiles" → clasificación por cuantiles
    """

    print(f"\nGenerando mapa ({modo_color})...")

    raster = rx.open_rasterio(raster_path, masked=True)

    if raster.ndim == 3:
        raster = raster.isel(band=0)

    if raster.rio.crs is None:
        raise ValueError("El raster no tiene CRS definido.")

    valores = raster.values
    valores = valores[~np.isnan(valores)]

    fig, ax = plt.subplots(figsize=(10, 10), facecolor="white")

    # ---------------------------------------------------
    # MODO CONTINUO
    # ---------------------------------------------------
    if modo_color == "percentiles":

        vmin, vmax = np.percentile(valores, [10, 90])

        im = raster.plot(
            ax=ax,
            cmap="RdYlGn_r",
            vmin=vmin,
            vmax=vmax,
            add_colorbar=True,
            cbar_kwargs={
                "label": "Índice de Impacto (Z-score)",
                "shrink": 0.7,
                "pad": 0.02,
            },
        )

        im.colorbar.set_ticks([vmin, vmax])

    # ---------------------------------------------------
    # MODO CUARTILES
    # ---------------------------------------------------
    elif modo_color == "cuartiles":

        cuantiles = np.percentile(valores, [0, 25, 50, 75, 100])

        cmap = plt.get_cmap("RdYlGn_r", 4)
        norm = BoundaryNorm(cuantiles, cmap.N)

        raster.plot(
            ax=ax,
            cmap=cmap,
            norm=norm,
            add_colorbar=True,
            cbar_kwargs={
                "label": "Índice (Cuartiles)",
                "ticks": cuantiles,
                "shrink": 0.7,
                "pad": 0.02,
            },
        )

    else:
        raise ValueError("modo_color debe ser 'percentiles' o 'cuartiles'")

    # ===================================================
    # VECTOR
    # ===================================================

    provincias = gpd.read_file(vector_path)

    if provincias.crs != raster.rio.crs:
        provincias = provincias.to_crs(raster.rio.crs)

    # ---------------------------------------------------
    # RECORTE MANUAL (NO MODIFICADO)
    # ---------------------------------------------------
    provincias_continentales = provincias.cx[:, -56.2:0]

    provincias_continentales.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#333333",
        linewidth=0.7,
        alpha=0.8,
    )

    # ---------------------------------------------------
    # LÍMITES MANUALES (NO MODIFICADO)
    # ---------------------------------------------------
    ax.set_ylim(-56.5, -17.0)
    ax.set_xlim(-76.0, -45.0)

    ax.set_title(
        "Áreas críticas de Vulnerabilidad al Cambio Climático",
        fontsize=15,
        pad=20,
    )

    ax.set_xlabel("Longitud", fontsize=10)
    ax.set_ylabel("Latitud", fontsize=10)

    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_major_locator(MultipleLocator(15))
    ax.grid(True, linestyle="--", alpha=0.2)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Mapa guardado en:\n{output_path}")


# ===================================================
# FUNCIÓN RADARES
# ===================================================


def crear_radares(
    excel_path,
    output_path,
    paises=None,
):
    """
    Genera gráfico comparativo tipo radar (top vs bottom).
    Guarda resultado con plt.savefig().
    """

    print("\nGenerando radares...")

    df = pd.read_excel(excel_path, sheet_name="Ranking Global de Riesgo")

    # ---------------------------------------------------
    # LIMPIEZA DE COLUMNAS
    # ---------------------------------------------------
    df.columns = df.columns.str.strip().str.lower()

    print("Columnas detectadas en el Excel:")
    print(df.columns.tolist())

    if paises is None:
        paises = ["paraguay", "uruguay", "brasil", "argentina"]

    # ---------------------------------------------------
    # DETECCIÓN AUTOMÁTICA DE COLUMNAS
    # ---------------------------------------------------

    posibles_z = ["z_bio1", "z_bio5", "z_bio14", "z_bio15"]
    posibles_mean = ["mean_bio_1", "mean_bio_5", "mean_bio_14", "mean_bio_15"]

    if all(col in df.columns for col in posibles_z):
        categorias_z = posibles_z
        print("Usando columnas Z-score.")
    elif all(col in df.columns for col in posibles_mean):
        categorias_z = posibles_mean
        print("Usando columnas mean_bio_*.")
    else:
        raise KeyError(
            "No se encontraron columnas compatibles para el radar.\n"
            f"Columnas disponibles:\n{df.columns.tolist()}"
        )

    # Validación de columnas
    missing = [col for col in categorias_z if col not in df.columns]

    if missing:
        raise KeyError(
            f"Las siguientes columnas no existen en el Excel: {missing}\n"
            f"Columnas disponibles: {df.columns.tolist()}"
        )

    nombres_eje = ["BIO1", "BIO5", "BIO14 (Sequía)", "BIO15"]

    colores_top = ["#e41a1c", "#ff7f00", "#984ea3", "#a65628", "#377eb8"]
    colores_bottom = ["#4daf4a", "#377eb8", "#a65628", "#984ea3", "#ff7f00"]

    # Normalizamos también nombre_zona
    if "nombre_zona" not in df.columns:
        raise KeyError("No existe la columna 'nombre_zona' en el Excel.")

    if "indice_consolidado" not in df.columns:
        raise KeyError("No existe la columna 'indice_consolidado' en el Excel.")

    df["nombre_zona"] = df["nombre_zona"].str.strip().str.lower()

    def plot_radar(ax, df_top, df_bottom, titulo):

        angles = np.linspace(0, 2 * pi, len(categorias_z), endpoint=False)
        angles = np.concatenate((angles, [angles[0]]))

        max_val = (
            max(
                df_top[categorias_z].abs().max().max(),
                df_bottom[categorias_z].abs().max().max(),
            )
            * 1.2
        )

        ax.set_theta_offset(pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(nombres_eje, fontsize=9)
        ax.set_rlim(-max_val, max_val)
        ax.set_title(titulo, fontsize=12, pad=18)

        for i, (_, row) in enumerate(df_top.iterrows()):
            values = row[categorias_z].tolist()
            values += values[:1]

            ax.plot(
                angles,
                values,
                linewidth=1.5,
                color=colores_top[i % len(colores_top)],
                label=f"{row['nombre_zona']} (Alto)",
            )
            ax.fill(angles, values, alpha=0.10)

        for i, (_, row) in enumerate(df_bottom.iterrows()):
            values = row[categorias_z].tolist()
            values += values[:1]

            ax.plot(
                angles,
                values,
                linewidth=1,
                linestyle="--",
                color=colores_bottom[i % len(colores_bottom)],
                label=f"{row['nombre_zona']} (Bajo)",
            )
            ax.fill(angles, values, alpha=0.10)

        ax.legend(
            loc="center left",
            bbox_to_anchor=(1.25, 0.5),
            fontsize=8,
            frameon=False,
        )

    # ---------------------------------------------------
    # FIGURA
    # ---------------------------------------------------

    plt.figure(figsize=(20, 11))
    gs = GridSpec(3, 2, height_ratios=[1, 1, 1.35])

    posiciones = [(0, 0), (0, 1), (1, 0), (1, 1)]

    for pais, (i, j) in zip(paises, posiciones):

        df_pais = (
            df[df["nombre_zona"] == pais]
            .sort_values("indice_consolidado", ascending=False)
            .copy()
        )

        if len(df_pais) < 3:
            continue

        top = df_pais.head(3)
        bottom = df_pais.tail(3).sort_values("indice_consolidado")

        ax = plt.subplot(gs[i, j], polar=True)

        plot_radar(
            ax=ax,
            df_top=top,
            df_bottom=bottom,
            titulo=f"{pais.upper()} – Top 3 Mayor / Menor Riesgo",
        )

    # ---------------------------------------------------
    # GLOBAL
    # ---------------------------------------------------

    df_global = df.sort_values("indice_consolidado", ascending=False)

    top_global = df_global.head(5)
    bottom_global = df_global.tail(5).sort_values("indice_consolidado")

    ax_global = plt.subplot(gs[2, :], polar=True)

    plot_radar(
        ax=ax_global,
        df_top=top_global,
        df_bottom=bottom_global,
        titulo="Sudamérica – Top 5 Mayor / Menor Riesgo Climático",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Radares guardados en:\n{output_path}")

# ===================================================
# EJECUCIÓN
# ===================================================

crear_mapa_indice(
    raster_path=IC_PATH,
    vector_path=VECTOR_PATH,
    output_path=MAP_OUTPUT_CUARTILES,
    modo_color="cuartiles",
)

crear_mapa_indice(
    raster_path=IC_PATH,
    vector_path=VECTOR_PATH,
    output_path=MAP_OUTPUT_PERCENTILES,
    modo_color="percentiles",
)

crear_radares(
    excel_path=EXCEL_PATH,
    output_path=RADAR_OUTPUT,
)










from adjustText import adjust_text

# ==========================================================
# 1. CARGA Y LIMPIEZA DE DATOS
# ==========================================================

# Eliminar NaN
df = df.dropna(subset=["IST", "ISH"]).copy()


# ==========================================================
# 2. CALCULAR PERCENTILES 90
# ==========================================================

p90_ist = df["I_estress_termico"].quantile(0.9)
p90_ish = df["I_estress_hidrico"].quantile(0.9)

# ==========================================================
# 3. CREAR FIGURA
# ==========================================================

fig, ax = plt.subplots(figsize=(12, 10))

colors = {
    "Argentina": "blue",
    "Uruguay": "green",
    "Brasil": "gold",
    "Paraguay": "red",
}

# ==========================================================
# 4. SCATTER POR PAÍS
# ==========================================================

for pais, color in colors.items():
    subset = df[df["pais"] == pais]

    ax.scatter(
        subset["I_estress_termico"],
        subset["I_estress_hidrico"],
        color=color,
        label=pais,
        alpha=0.7,
        s=60
    )

# ==========================================================
# 5. LÍNEAS DE REFERENCIA (P90)
# ==========================================================

ax.axvline(p90_ist, linestyle="--", color="gray")
ax.axhline(p90_ish, linestyle="--", color="gray")

# ==========================================================
# 6. PERSONALIZACIÓN
# ==========================================================

ax.set_xlabel("Índice de Estrés Térmico (IST)", fontsize=12)
ax.set_ylabel("Índice de Estrés Hídrico (ISH)", fontsize=12)

ax.set_title(
    "Hotspots de estrés térmico e hídrico en Cono Sur\n"
    "(2041–2060, SSP5-8.5)",
    fontsize=14
)

ax.grid(True, alpha=0.3)
ax.legend(title="País")

plt.tight_layout()
plt.savefig("scatter_IST_ISH.png", dpi=300)
plt.show()