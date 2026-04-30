from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterstats import zonal_stats

# ===================================================
# CONFIGURACIÓN GENERAL
# ===================================================

RASTER_PATH = Path("./RASTER/modificados/")
VECTOR_PATH = Path("./VECTOR/base_datos.gpkg")
OUTPUT_PATH = Path("./RASTER/derivados/")
OUTPUT_EXCEL = Path("./TABLES/")
if not OUTPUT_EXCEL.exists():
    OUTPUT_EXCEL.mkdir(exist_ok=True)
OUTPUT_EXCEL = OUTPUT_EXCEL.joinpath("Reporte_Hotspots_Area_Estudio.xlsx")
NODATA_VAL_OUT = 0

OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------
# VECTORES
# ---------------------------------------------------

regiones = gpd.read_file(VECTOR_PATH, layer='regiones')
regiones_adm = gpd.read_file(VECTOR_PATH, layer='regiones_administrativas')

# ---------------------------------------------------
# BIOS
# ---------------------------------------------------

BIOS = {
    1: {
        "name": "BIO1",
        "hist_path": RASTER_PATH.joinpath("recorte_wc2.1_30s_bio_1.tif"),
        "fut_path": RASTER_PATH.joinpath("recorte_bio_1_fut.tif"),
    },
    5: {
        "name": "BIO5",
        "hist_path": RASTER_PATH.joinpath("recorte_wc2.1_30s_bio_5.tif"),
        "fut_path": RASTER_PATH.joinpath("recorte_bio_5_fut.tif"),
    },
    14: {
        "name": "BIO14",
        "hist_path": RASTER_PATH.joinpath("recorte_wc2.1_30s_bio_14.tif"),
        "fut_path": RASTER_PATH.joinpath("recorte_bio_14_fut.tif"),
    },
    15: {
        "name": "BIO15",
        "hist_path": RASTER_PATH.joinpath("recorte_wc2.1_30s_bio_15.tif"),
        "fut_path": RASTER_PATH.joinpath("recorte_bio_15_fut.tif"),
    },
}

# ===================================================
# A.1 DELTAS BIOCLIMÁTICOS (STREAMING + BIO14 INVERTIDO)
# ===================================================
# todo add confirmacion si resultados ya existen y deberían ser overritten
for bio_idx, cfg in BIOS.items():
    # bio_idx, cfg = list(BIOS.items())[1]
    delta_path = OUTPUT_PATH.joinpath(f"DELTA_bio_{bio_idx}.tif")

    with rasterio.open(cfg["hist_path"]) as src_h, rasterio.open(
        cfg["fut_path"]
    ) as src_f:
        assert src_h.crs == src_f.crs
        assert src_h.transform == src_f.transform
        assert src_h.shape == src_f.shape

        profile = src_h.profile.copy()
        profile.update(dtype="float32", nodata=NODATA_VAL_OUT)

        with rasterio.open(delta_path, "w", **profile) as dst:
            for _, window in src_h.block_windows(1):
                h = src_h.read(1, window=window).astype("float32")
                f = src_f.read(1, window=window).astype("float32")

                delta = f - h

                mask = (h == src_h.nodata) | (f == src_f.nodata) | np.isnan(delta)

                delta[mask] = NODATA_VAL_OUT

                # Inversión temprana BIO14
                if bio_idx == 14:
                    delta = -delta

                dst.write(delta, 1, window=window)

    BIOS.get(bio_idx).update({"delta_path": delta_path})

    print(f"Delta bio_{bio_idx} generado")
    # ===================================================
    # A.2 MEDIA Y DESVIACIÓN REGIONAL (VECTORIAL)
    # ===================================================
    if regiones.crs != src_h.crs:
        regiones = regiones.to_crs(src_h.crs)
    if regiones_adm.crs != src_h.crs:
        regiones_adm = regiones_adm.to_crs(src_h.crs)

    stats = zonal_stats(
        regiones,
        cfg["hist_path"],
        stats=["mean", "std"],
        # nodata=NODATA_VAL_OUT,
        all_touched=True,
    )

    regiones[f"mean_hist_bio_{bio_idx}"] = [s["mean"] for s in stats]
    regiones[f"std_hist_bio_{bio_idx}"] = [s["std"] for s in stats]

    stats_adm = zonal_stats(
        regiones_adm,
        delta_path,
        stats=["mean", "std"],
        nodata=NODATA_VAL_OUT,
        all_touched=True,
    )

    regiones_adm[f"mean_bio_{bio_idx}"] = [s["mean"] for s in stats_adm]
    regiones_adm[f"std_bio_{bio_idx}"] = [s["std"] for s in stats_adm]

    if (regiones[f"std_hist_bio_{bio_idx}"] == 0).any():
        regiones.loc[regiones[f"std_hist_bio_{bio_idx}"] == 0, [f"std_hist_bio_{bio_idx}"]] = (
            -9999
        )
        # raise ValueError(f"STD = 0 detectado en BIO{bio_idx}")
        print(f"STD = 0 detectado en BIO{bio_idx}")

    print(f"Estadísticas regionales DELTA_bio_{bio_idx} calculadas")

    if (regiones_adm[f"std_bio_{bio_idx}"] == 0).any():
        regiones_adm.loc[
            regiones_adm[f"std_bio_{bio_idx}"] == 0,
            [f"std_bio_{bio_idx}"],
        ] = -9999

    print(f"Estadísticas administrativas DELTA_bio_{bio_idx} calculadas")

    # ===================================================
    # A.3 RASTERIZACIÓN DE MEDIA Y STD
    # ===================================================

    with rasterio.open(BIOS[1]["hist_path"]) as ref:
        meta = ref.meta.copy()
        meta.update(dtype="float32", nodata=NODATA_VAL_OUT)

        for stat in ["mean", "std"]:
            # stat = 'mean'
            out_path = OUTPUT_PATH.joinpath(f"{stat.upper()}_bio_{bio_idx}.tif")

            shapes = (
                (geom, val)
                for geom, val in zip(
                    regiones.geometry, regiones[f"{stat}_hist_bio_{bio_idx}"]
                )
            )

            raster = rasterize(
                shapes,
                out_shape=(ref.height, ref.width),
                transform=ref.transform,
                fill=NODATA_VAL_OUT,
                dtype="float32",
            )

            with rasterio.open(out_path, "w", **meta) as dst:
                dst.write(raster, 1)

            print(f"Raster {stat.upper()}_bio_{bio_idx} creado")
            BIOS.get(bio_idx).update({f"{stat}_path": out_path})
        # ===================================================
        # A.4 NORMALIZACIÓN Z-SCORE REGIONAL (STREAMING)
        # ===================================================

        mean_path = BIOS.get(bio_idx).get("mean_path")
        std_path = BIOS.get(bio_idx).get("std_path")
        z_path = OUTPUT_PATH.joinpath(f"Z_bio_{bio_idx}.tif")

    with rasterio.open(delta_path) as src_d, rasterio.open(
        mean_path
    ) as src_m, rasterio.open(std_path) as src_s:
        profile = src_d.profile.copy()
        profile.update(dtype="float32", nodata=NODATA_VAL_OUT)

        with rasterio.open(z_path, "w", **profile) as dst:
            for _, window in src_d.block_windows(1):
                d = src_d.read(1, window=window)
                m = src_m.read(1, window=window)
                s = src_s.read(1, window=window)

                z = np.full(d.shape, NODATA_VAL_OUT, dtype="float32")

                valid = (
                    (s != NODATA_VAL_OUT)
                    & (d != NODATA_VAL_OUT)
                    & (m != NODATA_VAL_OUT)
                    & (s != 0)
                )

                z[valid] = (d[valid] - m[valid]) / s[valid]

                dst.write(z, 1, window=window)

    BIOS.get(bio_idx).update({"z_path": z_path})

    print(f"Z-score bio_{bio_idx} generado")

# ===================================================
# A.5 ÍNDICES COMPUESTOS (STREAMING)
# ===================================================

print("\nGenerando índices compuestos (IST, ISH y Indice Consolidado)")

z1_path = BIOS[1]["z_path"]
z5_path = BIOS[5]["z_path"]
z14_path = BIOS[14]["z_path"]
z15_path = BIOS[15]["z_path"]

IST_PATH = OUTPUT_PATH.joinpath("IST.tif")
ISH_PATH = OUTPUT_PATH.joinpath("ISH.tif")
IC_PATH = OUTPUT_PATH.joinpath("Indice_Consolidado.tif")

with rasterio.open(z1_path) as src1, rasterio.open(z5_path) as src5, rasterio.open(
    z14_path
) as src14, rasterio.open(z15_path) as src15:

    profile = src1.profile.copy()
    profile.update(dtype="float32", nodata=NODATA_VAL_OUT)

    with rasterio.open(IST_PATH, "w", **profile) as dst_ist, rasterio.open(
        ISH_PATH, "w", **profile
    ) as dst_ish, rasterio.open(IC_PATH, "w", **profile) as dst_ic:

        for _, window in src1.block_windows(1):

            z1 = src1.read(1, window=window)
            z5 = src5.read(1, window=window)
            z14 = src14.read(1, window=window)
            z15 = src15.read(1, window=window)

            # Inicializar
            ist = np.full(z1.shape, NODATA_VAL_OUT, dtype="float32")
            ish = np.full(z1.shape, NODATA_VAL_OUT, dtype="float32")
            ic = np.full(z1.shape, NODATA_VAL_OUT, dtype="float32")

            # Máscara válida (todos deben ser válidos)
            valid = (
                (z1 != NODATA_VAL_OUT)
                & (z5 != NODATA_VAL_OUT)
                & (z14 != NODATA_VAL_OUT)
                & (z15 != NODATA_VAL_OUT)
            )

            # IST = Z1 + Z5
            ist[valid] = z1[valid] + z5[valid]

            # ISH = Z14 + Z15
            ish[valid] = z14[valid] + z15[valid]

            # Índice Consolidado
            ic[valid] = ist[valid] + ish[valid]

            dst_ist.write(ist, 1, window=window)
            dst_ish.write(ish, 1, window=window)
            dst_ic.write(ic, 1, window=window)

print("Índices compuestos generados correctamente.")


# ===================================================
# GENERAR EXCEL FINAL (MIX: DELTA + Z + ÍNDICES)
# ===================================================

print("\nGenerando Excel final coherente con raster...")

# Asegurar CRS coherente
with rasterio.open(IC_PATH) as src_ref:
    if regiones.crs != src_ref.crs:
        regiones = regiones.to_crs(src_ref.crs)

# ---------------------------------------------------
# FUNCIÓN AUXILIAR
# ---------------------------------------------------

def extraer_media(raster_path, nombre_columna):

    stats = zonal_stats(
        regiones_adm,
        raster_path,
        stats=["mean"],
        nodata=NODATA_VAL_OUT,
        all_touched=True,
    )

    regiones_adm[nombre_columna] = [s["mean"] for s in stats]


# ---------------------------------------------------
# EXTRAER Z-SCORES (DESDE RASTER)
# ---------------------------------------------------

extraer_media(BIOS[1]["z_path"], "z_bio_1")
extraer_media(BIOS[5]["z_path"], "z_bio_5")
extraer_media(BIOS[14]["z_path"], "z_bio_14")
extraer_media(BIOS[15]["z_path"], "z_bio_15")

# ---------------------------------------------------
# EXTRAER ÍNDICES COMPUESTOS (DESDE RASTER)
# ---------------------------------------------------

extraer_media(IST_PATH, "I_estress_termico")
extraer_media(ISH_PATH, "I_estress_hidrico")
extraer_media(IC_PATH, "Indice_consolidado")

# ---------------------------------------------------
# RANKING
# ---------------------------------------------------

ranking_df = (
    regiones_adm.sort_values(by="Indice_consolidado", ascending=False)
    .dropna(subset=["Indice_consolidado"])
    .reset_index(drop=True)
)

ranking_df["RANK"] = ranking_df.index + 1
ranking_df.to_file(VECTOR_PATH, layer='regiones_adm_resultado')

# ---------------------------------------------------
# EXPORTAR (INCLUYE MEAN Y STD ORIGINALES)
# ---------------------------------------------------
cols_excel = [
    "RANK",
    "nombre",
    "pais",
    "REGION",
    "I_estress_termico",
    "I_estress_hidrico",
    "Indice_consolidado",
    "z_bio_1",
    "z_bio_5",
    "z_bio_14",
    "z_bio_15",
    "mean_bio_1",
    "mean_bio_5",
    "mean_bio_14",
    "mean_bio_15",
    "std_bio_1",
    "std_bio_5",
    "std_bio_14",
    "std_bio_15",
]


with pd.ExcelWriter(OUTPUT_EXCEL, engine="xlsxwriter") as writer:
    ranking_df.to_excel(
        writer,
        sheet_name="Ranking Global de Riesgo",
        index=False,
        columns=cols_excel,
    )

print(f"Excel generado correctamente en:\n{OUTPUT_EXCEL}")
print("\nDelta, Normalización Z-score y XLSX creados")
