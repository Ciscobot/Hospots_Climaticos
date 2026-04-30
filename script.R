library(ggplot2)
library(dplyr)
library(readxl)
library(tidyr)
library(ggrepel)

# Cargar datos
df <- read_excel("./TABLES/Reporte_Hotspots_Area_Estudio.xlsx")
colnames(df)
# Eliminar posibles NA
df <- df %>%
  filter(!is.na(I_estress_termico),
         !is.na(I_estress_hidrico))

# Calcular percentiles 90
q_ist <- quantile(df$I_estress_termico, probs = 0.9, na.rm = TRUE)
q_ish <- quantile(df$I_estress_hidrico, probs = 0.9, na.rm = TRUE)

# Clasificación de hotspots
df <- df %>%
  mutate(tipo_hotspot = case_when(
    I_estress_termico >= q_ist & I_estress_hidrico >= q_ish ~ "Combined hotspot",
    I_estress_termico >= q_ist ~ "Thermal hotspot",
    I_estress_hidrico >= q_ish ~ "Water hotspot",
    TRUE ~ "Low/Moderate"
  ))

# Crear gráfico
p <- ggplot(df, aes(x = I_estress_termico, y = I_estress_hidrico)) +
  
  geom_point(aes(color = tipo_hotspot),
             size = 3,
             alpha = 0.8) +
  
  # Líneas de percentil 90
  geom_vline(xintercept = q_ist, linetype = "dashed", color = "grey40") +
  geom_hline(yintercept = q_ish, linetype = "dashed", color = "grey40") +
  
  # Etiquetas solo para hotspots
  geom_text_repel(
    data = subset(df, tipo_hotspot != "Low/Moderate"),
    aes(label = nombre),
    size = 3.5,
    box.padding = 0.3,
    point.padding = 0.3,
    segment.color = "grey50"
  ) +
  
  scale_color_manual(values = c(
    "Combined hotspot" = "red3",
    "Thermal hotspot" = "orange",
    "Water hotspot" = "blue3",
    "Low/Moderate" = "grey70"
  )) +
  
  labs(
    title = "",
    x = "Thermal Stress Index (IST)",
    y = "Water Stress Index (ISW)",
    color = "Condition"
  ) +
  
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", hjust = 0.5),
    legend.position = "right"
  )

# Guardar figura
ggsave("Figura_Hotspots_IST_ISH_en.png",
       plot = p,
       width = 10,
       height = 6,
       dpi = 300,
       units = "in")

p

### Grafico de delta y std ----

df_long <- df %>%
  select(nombre, pais,
         mean_bio_1, mean_bio_5, mean_bio_14, mean_bio_15,
         std_bio_1,  std_bio_5,  std_bio_14,  std_bio_15) %>%
  
  # Pasar a formato largo
  pivot_longer(
    cols = -c(nombre, pais),
    names_to = c(".value", "bio"),
    names_pattern = "(mean|std)_bio_(.*)"
  ) %>%
  
  # Eliminar NA
  filter(!is.na(mean), !is.na(std))

# Calcular medianas por variable
cuts <- df_long %>%
  group_by(bio) %>%
  summarise(
    cut_delta = median(mean, na.rm = TRUE),
    cut_sigma = median(std, na.rm = TRUE)
  )

# Unir cortes al dataframe
df_long <- df_long %>%
  left_join(cuts, by = "bio")

# Crear gráfico con facetas
p <- ggplot(df_long,
            aes(x = mean,
                y = std,
                color = pais)) +
  
  geom_point(size = 2.8, alpha = 0.8) +
  
  geom_vline(aes(xintercept = cut_delta),
             linetype = "dashed",
             color = "grey40") +
  
  geom_hline(aes(yintercept = cut_sigma),
             linetype = "dashed",
             color = "grey40") +
  
  facet_wrap(~ bio, 
           ncol = 2,
           scales = "free",
             labeller = labeller(
               bio = c(
                 "1"  = "BIO1 – Annual Mean Temperature",
                 "5"  = "BIO5 – Max Temperature of Warmest Month",
                 "14" = "BIO14 – Precipitation of Driest Month",
                 "15" = "BIO15 – Precipitation Seasonality"
               )
             )) +
  
  labs(
    title = "",
    x = expression(Delta*" Absolute change"),
    y = expression(sigma*" Historical variability"),
    color = "Country"
  ) +
  
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", hjust = 0.5),
    legend.position = "bottom"
  )

# Guardar figura
ggsave("Grid_QuadrantPlots_BIOs_en.png",
       plot = p,
       width = 10,
       height = 6,
       dpi = 300,
       units = "in")

p
