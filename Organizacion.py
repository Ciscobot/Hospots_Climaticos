import rasterio
import os


future_raster_path = (
    "./RASTER/originales/wc2.1_30s_bioc_IPSL-CM6A-LR_ssp585_2021-2040.tif"
)
bandas = [1, 4, 14, 15]

for banda in bandas:
    salida = f"./RASTER/originales/bio{banda}_fut.tif"
    if not os.path.exists(future_raster_path):
        print("ERROR: raster no encontrado")
    else:
        with rasterio.open(future_raster_path) as src:
            if banda > src.count:
                raise ValueError("La banda no existe")

            profile = src.profile.copy()
            profile.update(count=1)

            with rasterio.open(salida, "w", **profile) as dst:
                # Itera sobre los bloques internos del raster
                for _, window in src.block_windows(banda):
                    data = src.read(banda, window=window)
                    dst.write(data, 1, window=window)
        print(f"Raster {salida} exportado con exito.")
