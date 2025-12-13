import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
import numpy as np
from pathlib import Path

REQUIERE_REPROJECT = {"CRS", "RES", "ORIGIN", "EXTENT", "DIMENSIONS"}
NODATA = -9999

raster_path = Path("./RASTER/modificados")
raster_ref = raster_path.joinpath("recorte_wc2.1_30s_bio_1.tif")
if not raster_ref.exists():
    print("ERROR: Raster referencia no encontrado")

rasters_to_validate = [r for r in raster_path.glob("recorte_*.tif") if r != raster_ref]
raster_out_name = "_ali.tif"


def valida_alineacion(r_path, r_ref, tol=1e-6):
    problems = set()

    with rasterio.open(r_path) as r1, rasterio.open(r_ref) as ref:
        if r1.crs != ref.crs:
            problems.add("CRS")

        if not np.allclose(r1.res, ref.res, atol=tol):
            problems.add("RES")

        if not np.allclose(
            (r1.transform.c, r1.transform.f),
            (ref.transform.c, ref.transform.f),
            atol=tol,
        ):
            problems.add("ORIGIN")

        if not np.allclose(r1.bounds, ref.bounds, atol=tol):
            problems.add("EXTENT")

        if (r1.width != ref.width) or (r1.height != ref.height):
            problems.add("DIMENSIONS")

    return problems


results = {}

for raster in rasters_to_validate:
    problems = valida_alineacion(raster, raster_ref)
    if problems:
        results[raster] = problems

for raster_in, problems in results.items():
    if not problems & REQUIERE_REPROJECT:
        print(f"{raster_in.name}: no requiere reproyección")
        continue

    print(f"{raster_in.name}: corrigiendo {sorted(problems)}")

    salida_raster = raster_in.with_name(raster_in.stem + "_ali.tif")

    # Raster referencia
    with rasterio.open(raster_ref) as ref:
        ref_crs = ref.crs
        ref_transform = ref.transform
        ref_width = ref.width
        ref_height = ref.height
        ref_bounds = ref.bounds

    # Raster origen
    with rasterio.open(raster_in) as src:
        src_data = src.read(1)

        dst_transform = from_bounds(
            ref_bounds.left,
            ref_bounds.bottom,
            ref_bounds.right,
            ref_bounds.top,
            ref_width,
            ref_height,
        )

        dst_data = np.full((ref_height, ref_width), NODATA, dtype=np.float32)

        reproject(
            source=src_data,
            destination=dst_data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear,
            src_nodata=src.nodata,
            dst_nodata=NODATA,
        )

    profile = {
        "driver": "GTiff",
        "height": ref_height,
        "width": ref_width,
        "count": 1,
        "dtype": "float32",
        "crs": ref_crs,
        "transform": dst_transform,
        "nodata": NODATA,
        "compress": "lzw",
        "tiled": True,
    }

    with rasterio.open(salida_raster, "w", **profile) as dst:
        dst.write(dst_data, 1)

    print(f"✔ Guardado: {salida_raster.name}")
