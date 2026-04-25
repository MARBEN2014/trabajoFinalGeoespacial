import streamlit as st
import pandas as pd
import folium
import geopandas as gpd
from streamlit_folium import st_folium
from folium.plugins import HeatMap, MarkerCluster
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# Configuración de página
st.set_page_config(page_title="Dashboard Ventas RM - Diego Vásquez", layout="wide")

# 1. Carga de datos con caché y limpieza de comas
@st.cache_data
def load_data():
    nombre_archivo = "dataset_tarea_ind.xlsx"
    df = pd.read_excel(nombre_archivo, engine='openpyxl')
    
    # Limpieza de columnas numéricas (Convertir '65357,98' a 65357.98)
    cols_a_limpiar = ['venta_neta', 'lat', 'lng', 'kms_dist', 'lat_cd', 'lng_cd', 'unidades']
    for col in cols_a_limpiar:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    # Convertir fecha a datetime
    df['fecha_compra'] = pd.to_datetime(df['fecha_compra'], dayfirst=True)
    
    # Eliminar nulos en coordenadas críticas
    df = df.dropna(subset=['lat', 'lng'])
    
    # Normalización de nombres de comuna
    df['comuna'] = df['comuna'].str.upper().str.strip()
    return df

@st.cache_data
def load_geojson():
    geo = gpd.read_file("comunas_metropolitana-1.geojson")
    geo['name'] = geo['name'].str.upper().str.strip()
    return geo

# Carga inicial
try:
    df = load_data()
    geo_data = load_geojson()
except Exception as e:
    st.error(f"Error al cargar archivos: {e}")
    st.stop()

# --- SIDEBAR (Filtros Globales) ---
st.sidebar.header("Filtros de Análisis")
canal_selected = st.sidebar.multiselect(
    "Seleccione Canal de Venta:",
    options=df['canal'].unique(),
    default=df['canal'].unique()
)

min_v = int(df['venta_neta'].min())
max_v = int(df['venta_neta'].max())
rango_venta = st.sidebar.slider("Rango de Venta Neta ($):", min_v, max_v, (min_v, max_v))

# Aplicar filtros
df_filtered = df[
    (df['canal'].isin(canal_selected)) & 
    (df['venta_neta'] >= rango_venta[0]) & 
    (df['venta_neta'] <= rango_venta[1])
]

# --- CUERPO PRINCIPAL ---
st.title("📊 Dashboard de Inteligencia Logística - RM")
st.markdown(f"**Analista:** Diego Vásquez Orellana")

# KPIs rápidos
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Venta Total Filtrada", f"$ {df_filtered['venta_neta'].sum():,.0f}")
with k2:
    st.metric("Total Pedidos", f"{len(df_filtered):,}")
with k3:
    st.metric("Ticket Promedio", f"$ {df_filtered['venta_neta'].mean():,.0f}")

# Pestañas
tab1, tab2 = st.tabs(["🗺️ Explorador Geoespacial Avanzado", "📈 Análisis Estadístico"])

with tab1:
    st.subheader("Visualización de Capas Geográficas")
    
    # Selector de tipo de mapa (Punto b: interactividad que mejora la exploración)
    tipo_mapa = st.selectbox(
        "Seleccione el tipo de análisis visual:",
        ["Red Logística (CDs y Entregas)", 
         "Calor: Densidad de Pedidos", 
         "Calor: Intensidad Económica (Ventas)", 
         "Coropleta: Venta Neta por Comuna"]
    )
    
    # Mapa Base
    m = folium.Map(location=[-33.45694, -70.64827], zoom_start=11, tiles='cartodbpositron')

    if tipo_mapa == "Red Logística (CDs y Entregas)":
        # 1. Agregar CDs (Puntos únicos)
        cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])
        for _, row in cds_unicos.iterrows():
            folium.Marker(
                location=[row['lat_cd'], row['lng_cd']],
                popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                tooltip=row['centro_dist'],
                icon=folium.Icon(color='red', icon='home', prefix='fa')
            ).add_to(m)
        
        # 2. Cluster de clientes (muestra de 1000 según tip 3)
        muestra = df_filtered.sample(n=min(1000, len(df_filtered)), random_state=42)
        marker_cluster = MarkerCluster(name="Entregas").add_to(m)
        for _, row in muestra.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lng']],
                radius=3, color='blue', fill=True, fill_opacity=0.6,
                popup=f"Venta: ${row['venta_neta']:.0f}"
            ).add_to(marker_cluster)

    elif tipo_mapa == "Calor: Densidad de Pedidos":
        data_cantidad = df_filtered[['lat', 'lng']].values.tolist()
        HeatMap(data_cantidad, radius=12, blur=8, min_opacity=0.4,
                gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(m)

    elif tipo_mapa == "Calor: Intensidad Económica (Ventas)":
        # Normalización para el gradiente
        max_v_f = df_filtered['venta_neta'].max() if not df_filtered.empty else 1
        df_filtered['venta_norm'] = df_filtered['venta_neta'] / max_v_f
        data_venta = df_filtered[['lat', 'lng', 'venta_norm']].values.tolist()
        HeatMap(data_venta, radius=15, blur=10, min_opacity=0.5).add_to(m)

    elif tipo_mapa == "Coropleta: Venta Neta por Comuna":
        ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
        choropleth = folium.Choropleth(
            geo_data=geo_data,
            data=ventas_comuna,
            columns=["comuna", "venta_neta"],
            key_on="feature.properties.name",
            fill_color="YlGnBu",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name="Venta Neta Total ($)",
            highlight=True
        ).add_to(m)
        
        # Tooltips corregidos del Notebook
        v_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()
        for feature in choropleth.geojson.data['features']:
            nom = feature['properties']['name']
            v = v_dict.get(nom, 0)
            feature['properties']['Venta_Total_Fmt'] = f"$ {v:,.0f}"

        choropleth.geojson.add_child(
            folium.features.GeoJsonTooltip(
                fields=['name', 'Venta_Total_Fmt'], 
                aliases=['Comuna:', 'Ventas Totales:'],
                localize=True
            )
        )

    # Renderizado (Tip 2: returned_objects=[])
    st_folium(m, width="100%", height=600, returned_objects=[])

with tab2:
    st.subheader("Visualizaciones Estadísticas Clave")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.write("#### Proporción de Pedidos por Canal")
        canal_counts = df_filtered['canal'].value_counts()
        fig1, ax1 = plt.subplots(figsize=(8, 6))
        colors = sns.color_palette('viridis', len(canal_counts))
        ax1.pie(canal_counts, labels=canal_counts.index, autopct='%1.1f%%',
                colors=colors, startangle=140, wedgeprops={'edgecolor': 'white'})
        ax1.add_artist(plt.Circle((0, 0), 0.30, fc='white'))
        st.pyplot(fig1)

    with col_b:
        st.write("#### Venta Neta por Centro de Distribución")
        cd_sales = df_filtered.groupby('centro_dist')['venta_neta'].sum().sort_values(ascending=False).reset_index()
        fig2, ax2 = plt.subplots(figsize=(10, 7.5))
        sns.barplot(data=cd_sales, x='venta_neta', y='centro_dist', hue='centro_dist', palette='viridis', legend=False, ax=ax2)
        ax2.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'{x/1e6:.1f}M'))
        st.pyplot(fig2)

    st.write("#### Evolución Temporal de Unidades Vendidas")
    temporal_sales = df_filtered.groupby('fecha_compra')['unidades'].sum().reset_index()
    fig3, ax3 = plt.subplots(figsize=(14, 5))
    sns.lineplot(data=temporal_sales, x='fecha_compra', y='unidades', marker='o', color='#21918c', ax=ax3)
    plt.xticks(rotation=45)
    st.pyplot(fig3)

# --- REFLEXIÓN ---
st.divider()
with st.expander("Ver Reflexión Académica"):
    st.markdown("""
    **¿Qué interactividad agregamos y por qué mejora la exploración?**
    1. **Selector de Capas Geográficas:** Permite al usuario cambiar el enfoque del análisis (de logística a ventas o densidad) en un mismo espacio, facilitando la comparación mental de los fenómenos.
    2. **Filtros Dinámicos:** Los sliders y multiselectores actualizan todos los mapas y gráficos al unísono, permitiendo identificar si los patrones de calor cambian según el volumen de venta.
    3. **Optimización de Rendimiento:** Se aplicó muestreo (Sampling) y Clusters para los puntos de entrega, junto con `returned_objects=[]` en Folium para asegurar que la navegación sea fluida y profesional.
    """)