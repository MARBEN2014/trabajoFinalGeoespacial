import streamlit as st
import pandas as pd
import folium
import geopandas as gpd
from streamlit_folium import st_folium
from folium.plugins import HeatMap, MarkerCluster
import seaborn as sns
import matplotlib.pyplot as plt

# Configuración de página
st.set_page_config(page_title="Dashboard Ventas RM - Diego Vásquez", layout="wide")

# 1. Carga de datos con caché y limpieza de comas
@st.cache_data
def load_data():
    nombre_archivo = "dataset_tarea_ind.xlsx"
    # Cargamos el Excel
    df = pd.read_excel(nombre_archivo, engine='openpyxl')
    
    # --- TU LÓGICA DE LIMPIEZA INTEGRADA ---
    cols_a_limpiar = ['venta_neta', 'lat', 'lng', 'kms_dist', 'lat_cd', 'lng_cd']
    for col in cols_a_limpiar:
        if col in df.columns:
            # Reemplazamos coma por punto y convertimos a float de forma segura
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    # Eliminar nulos en coordenadas críticas para evitar errores en el mapa
    df = df.dropna(subset=['lat', 'lng'])
    
    # Normalización de nombres de comuna para el cruce con GeoJSON
    df['comuna'] = df['comuna'].str.upper().str.strip()
    return df

@st.cache_data
def load_geojson():
    geo = gpd.read_file("comunas_metropolitana-1.geojson")
    geo['name'] = geo['name'].str.upper().str.strip()
    return geo

# Carga inicial de datos
try:
    df = load_data()
    geo_data = load_geojson()
except Exception as e:
    st.error(f"Error al cargar archivos: {e}")
    st.stop()

# --- SIDEBAR (Filtros) ---
st.sidebar.header("Filtros de Análisis")
canal_selected = st.sidebar.multiselect(
    "Seleccione Canal de Venta:",
    options=df['canal'].unique(),
    default=df['canal'].unique()
)

# Filtro por rango de venta
min_v = int(df['venta_neta'].min())
max_v = int(df['venta_neta'].max())
rango_venta = st.sidebar.slider("Rango de Venta Neta ($):", min_v, max_v, (min_v, max_v))

# Aplicar filtros
df_filtered = df[
    (df['canal'].isin(canal_selected)) & 
    (df['venta_neta'] >= rango_venta[0]) & 
    (df['venta_neta'] <= rango_venta[1])
]

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Dashboard de Inteligencia Logística - RM")
st.markdown(f"**Alumno:** Diego Vásquez Orellana")

# Indicadores Clave (KPIs)
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Venta Total Filtrada", f"$ {df_filtered['venta_neta'].sum():,.0f}")
with k2:
    st.metric("Total Pedidos", f"{len(df_filtered):,}")
with k3:
    st.metric("Ticket Promedio", f"$ {df_filtered['venta_neta'].mean():,.0f}")

# Pestañas de Navegación
tab1, tab2 = st.tabs(["🗺️ Mapa Híbrido (Calor + Coropleta)", "📈 Análisis Estadístico"])

with tab1:
    st.subheader("Intensidad de Pedidos y Valor Económico por Comuna")
    
    # Preparar datos para la Coropleta
    ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
    ventas_comuna['venta_mm'] = ventas_comuna['venta_neta'] / 1_000_000
    
    # Crear el mapa base
    m = folium.Map(location=[-33.4569, -70.6482], zoom_start=10, tiles='cartodbpositron')
    
    # 1. Capa Coropleta (YlGn)
    choropleth = folium.Choropleth(
        geo_data=geo_data,
        data=ventas_comuna,
        columns=["comuna", "venta_mm"],
        key_on="feature.properties.name",
        fill_color="YlGn",
        fill_opacity=0.4,
        line_opacity=0.2,
        legend_name="Venta Total (MM$)",
        highlight=True
    ).add_to(m)

    # 2. Tooltips Interactivos
    v_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()
    for feature in choropleth.geojson.data['features']:
        name = feature['properties']['name']
        val = v_dict.get(name, 0)
        feature['properties']['info'] = f"Comuna: {name} | Venta: $ {val:,.0f}"

    choropleth.geojson.add_child(
        folium.features.GeoJsonTooltip(fields=['info'], labels=False, sticky=True)
    )

    # 3. Capa HeatMap (Densidad)
    heat_data = df_filtered[['lat', 'lng']].values.tolist()
    HeatMap(heat_data, radius=12, blur=18, min_opacity=0.3, 
            gradient={0.4: 'blue', 0.6: 'purple', 1: 'red'}).add_to(m)

    # Renderizado optimizado
    st_folium(m, width=1100, height=600, returned_objects=[])

with tab2:
    st.subheader("Desempeño de Ventas por Canal y Territorio")
    c1, c2 = st.columns(2)
    
    with c1:
        fig_box, ax_box = plt.subplots()
        sns.boxplot(data=df_filtered, x='canal', y='venta_neta', palette='Set2', ax=ax_box)
        ax_box.set_title("Distribución de Venta por Canal")
        st.pyplot(fig_box)
        
    with c2:
        top_comunas = df_filtered.groupby('comuna')['venta_neta'].sum().sort_values(ascending=False).head(10)
        fig_bar, ax_bar = plt.subplots()
        top_comunas.plot(kind='barh', color='skyblue', ax=ax_bar)
        ax_bar.set_title("Top 10 Comunas por Facturación")
        ax_bar.invert_yaxis()
        st.pyplot(fig_bar)

# --- REFLEXIÓN FINAL ---
st.divider()
with st.expander("Ver Reflexión Académica"):
    st.markdown("""
    **¿Qué interactividad agregamos y por qué mejora la exploración?**
    1. **Filtros Dinámicos:** Permiten aislar comportamientos específicos de la App vs el Sitio Web.
    2. **Mapa Híbrido:** La combinación de calor y coropleta permite ver simultáneamente el volumen de logística (pedidos) y el rendimiento financiero (ventas).
    3. **Optimización con Caché:** El uso de `@st.cache_data` permite que la aplicación sea fluida a pesar de procesar archivos GeoJSON y Excel con miles de registros.
    """)