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
    
    # Limpieza de columnas numéricas
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

# --- SIDEBAR (Filtros Avanzados) ---
st.sidebar.header("🎯 Filtros de Inteligencia")

# Botón para limpiar filtros
if st.sidebar.button("🔄 Resetear Filtros"):
    st.rerun()

# Filtro 1: Canal de Venta
canal_selected = st.sidebar.multiselect(
    "Canal de Venta:",
    options=sorted(df['canal'].unique()),
    default=df['canal'].unique()
)

# Filtro 2: Centro de Distribución
cd_selected = st.sidebar.multiselect(
    "Centro de Distribución (CD):",
    options=sorted(df['centro_dist'].unique()),
    default=df['centro_dist'].unique()
)

# Filtro 3: Comunas
comuna_selected = st.sidebar.multiselect(
    "Comunas de Entrega:",
    options=sorted(df['comuna'].unique()),
    default=df['comuna'].unique()
)

# Filtro 4: Rango de Fechas
st.sidebar.subheader("Rango Temporal")
min_date = df['fecha_compra'].min().date()
max_date = df['fecha_compra'].max().date()
fecha_rango = st.sidebar.date_input("Seleccione Periodo:", [min_date, max_date])

# Filtro 5: Rango de Ventas
min_v = int(df['venta_neta'].min())
max_v = int(df['venta_neta'].max())
rango_venta = st.sidebar.slider("Valor de Venta Neta ($):", min_v, max_v, (min_v, max_v))

# APLICACIÓN DE FILTROS CRUZADOS
mask = (
    (df['canal'].isin(canal_selected)) &
    (df['centro_dist'].isin(cd_selected)) &
    (df['comuna'].isin(comuna_selected)) &
    (df['venta_neta'] >= rango_venta[0]) &
    (df['venta_neta'] <= rango_venta[1])
)

# Aplicar filtro de fecha solo si se seleccionó un rango válido
if len(fecha_rango) == 2:
    mask = mask & (df['fecha_compra'].dt.date >= fecha_rango[0]) & (df['fecha_compra'].dt.date <= fecha_rango[1])

df_filtered = df[mask]

# --- CUERPO PRINCIPAL ---
st.title(" Dashboard  ")
st.title(" VisualizaciónDatos Geoespaciales ")
st.markdown(f"**Alumno:** Diego Vásquez Orellana")

# KPIs dinámicos
if not df_filtered.empty:
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Venta Total Filtrada", f"$ {df_filtered['venta_neta'].sum():,.0f}")
    with k2:
        st.metric("Total Pedidos", f"{len(df_filtered):,}")
    with k3:
        st.metric("Ticket Promedio", f"$ {df_filtered['venta_neta'].mean():,.0f}")
else:
    st.warning("⚠️ No hay datos para los filtros seleccionados.")

# Pestañas
tab1, tab2 = st.tabs([" Visualización Geoespacial", " Análisis Estadístico"])

with tab1:
    tipo_mapa = st.selectbox(
        "Seleccione Capa de Análisis:",
        ["Red Logística (CDs y Entregas)", 
         "Calor: Densidad de Pedidos", 
         "Calor: Intensidad Económica (Ventas)", 
         "Coropleta: Venta Neta por Comuna"]
    )
    
    m = folium.Map(location=[-33.45694, -70.64827], zoom_start=11, tiles='cartodbpositron')

    if not df_filtered.empty:
        if tipo_mapa == "Red Logística (CDs y Entregas)":
            # CDs Únicos filtrados
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])
            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"CD: {row['centro_dist']}",
                    icon=folium.Icon(color='red', icon='home', prefix='fa')
                ).add_to(m)
            
            # Cluster Clientes (Sampling para rendimiento)
            muestra = df_filtered.sample(n=min(1000, len(df_filtered)), random_state=42)
            marker_cluster = MarkerCluster(name="Entregas").add_to(m)
            for _, row in muestra.iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lng']],
                    radius=3, color='blue', fill=True, fill_opacity=0.6,
                    popup=f"Venta: ${row['venta_neta']:.0f}"
                ).add_to(marker_cluster)

        elif tipo_mapa == "Calor: Densidad de Pedidos":
            HeatMap(df_filtered[['lat', 'lng']].values.tolist(), radius=12, blur=8).add_to(m)

        elif tipo_mapa == "Calor: Intensidad Económica (Ventas)":
            max_val = df_filtered['venta_neta'].max()
            df_filtered['venta_norm'] = df_filtered['venta_neta'] / max_val
            HeatMap(df_filtered[['lat', 'lng', 'venta_norm']].values.tolist(), radius=15, blur=10).add_to(m)

        elif tipo_mapa == "Coropleta: Venta Neta por Comuna":
            ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
            choropleth = folium.Choropleth(
                geo_data=geo_data, data=ventas_comuna,
                columns=["comuna", "venta_neta"], key_on="feature.properties.name",
                fill_color="YlGnBu", fill_opacity=0.7, line_opacity=0.2
            ).add_to(m)
            
            v_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()
            for feature in choropleth.geojson.data['features']:
                name = feature['properties']['name']
                v = v_dict.get(name, 0)
                feature['properties']['Venta_Total_Fmt'] = f"$ {v:,.0f}"

            choropleth.geojson.add_child(
                folium.features.GeoJsonTooltip(fields=['name', 'Venta_Total_Fmt'], aliases=['Comuna:', 'Ventas:'])
            )

    st_folium(m, width="100%", height=600, returned_objects=[])

with tab2:
    if not df_filtered.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### Distribución por Canal")
            canal_counts = df_filtered['canal'].value_counts()
            fig1, ax1 = plt.subplots()
            ax1.pie(canal_counts, labels=canal_counts.index, autopct='%1.1f%%', colors=sns.color_palette('viridis', len(canal_counts)))
            ax1.add_artist(plt.Circle((0,0), 0.4, fc='white'))
            st.pyplot(fig1)

        with c2:
            st.write("#### Ventas por Centro de Distribución")
            cd_sales = df_filtered.groupby('centro_dist')['venta_neta'].sum().sort_values(ascending=False)
            fig2, ax2 = plt.subplots()
            sns.barplot(x=cd_sales.values, y=cd_sales.index, palette='viridis', ax=ax2)
            ax2.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'{x/1e6:.1f}M'))
            st.pyplot(fig2)

        st.write("#### Evolución de Unidades Vendidas")
        temporal = df_filtered.groupby('fecha_compra')['unidades'].sum().reset_index()
        fig3, ax3 = plt.subplots(figsize=(12, 4))
        sns.lineplot(data=temporal, x='fecha_compra', y='unidades', marker='o', color='#21918c', ax=ax3)
        plt.xticks(rotation=45)
        st.pyplot(fig3)
    else:
        st.info("Ajuste los filtros para visualizar los gráficos.")

# --- REFLEXIÓN ---
st.divider()
with st.expander("Ver Reflexión Académica"):
    st.markdown("""
    **Mejoras en la Exploración Mediante Filtros Avanzados:**
    1. **Filtro de Fecha:** Esencial para detectar estacionalidad (ej. días de mayor demanda en la RM).
    2. **Filtros de Ubicación (Comuna/CD):** Permite analizar la eficiencia logística por zona. Un CD podría estar saturado mientras otro tiene baja demanda.
    3. **Interactividad Cruzada:** Al filtrar por CD, el mapa de calor muestra exactamente el área de influencia de esa bodega, permitiendo detectar 'solapamientos' o zonas descuidadas.
    """)