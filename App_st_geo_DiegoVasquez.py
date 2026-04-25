import streamlit as st
import pandas as pd
import folium
import geopandas as gpd
from streamlit_folium import st_folium
from folium.plugins import HeatMap
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
    
    # Convertir fecha a datetime para el gráfico temporal
    df['fecha_compra'] = pd.to_datetime(df['fecha_compra'], dayfirst=True)
    
    # Eliminar nulos en coordenadas críticas
    df = df.dropna(subset=['lat', 'lng'])
    
    # Normalización de comunas
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

min_v = int(df['venta_neta'].min())
max_v = int(df['venta_neta'].max())
rango_venta = st.sidebar.slider("Rango de Venta Neta ($):", min_v, max_v, (min_v, max_v))

# Aplicar filtros dinámicos
df_filtered = df[
    (df['canal'].isin(canal_selected)) & 
    (df['venta_neta'] >= rango_venta[0]) & 
    (df['venta_neta'] <= rango_venta[1])
]

# --- DASHBOARD PRINCIPAL ---
st.title("📊 Dashboard de Inteligencia Logística - RM")
st.markdown(f"**Analista:** Diego Vásquez Orellana")

# Indicadores Clave (KPIs)
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Venta Total Filtrada", f"$ {df_filtered['venta_neta'].sum():,.0f}")
with k2:
    st.metric("Total Pedidos", f"{len(df_filtered):,}")
with k3:
    st.metric("Total Unidades Vendidas", f"{int(df_filtered['unidades'].sum()):,}")

# Pestañas de Navegación
tab1, tab2 = st.tabs(["🗺️ Mapa Híbrido Avanzado", "📈 Análisis Estadístico del Notebook"])

with tab1:
    st.subheader("Intensidad de Pedidos y Valor Económico por Comuna")
    
    ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
    ventas_comuna['venta_mm'] = ventas_comuna['venta_neta'] / 1_000_000
    
    m = folium.Map(location=[-33.4569, -70.6482], zoom_start=10, tiles='cartodbpositron')
    
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

    v_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()
    for feature in choropleth.geojson.data['features']:
        name = feature['properties']['name']
        val = v_dict.get(name, 0)
        feature['properties']['info'] = f"Comuna: {name} | Venta: $ {val:,.0f}"

    choropleth.geojson.add_child(
        folium.features.GeoJsonTooltip(fields=['info'], labels=False, sticky=True)
    )

    heat_data = df_filtered[['lat', 'lng']].values.tolist()
    HeatMap(heat_data, radius=12, blur=18, min_opacity=0.3, 
            gradient={0.4: 'blue', 0.6: 'purple', 1: 'red'}).add_to(m)

    st_folium(m, width=1100, height=600, returned_objects=[])

with tab2:
    st.subheader("Visualizaciones Estadísticas Clave")
    
    # Fila 1: Distribución por Canal (Pie Chart) y Ventas por CD (Bar Chart)
    col_a, col_b = st.columns(2)
    
    with col_a:
        # Gráfico 1: Pie Chart (Donut) del Canal
        st.write("#### Proporción de Ventas por Canal")
        canal_counts = df_filtered['canal'].value_counts()
        fig1, ax1 = plt.subplots(figsize=(8, 6))
        colors = sns.color_palette('viridis', len(canal_counts))
        wedges, texts, autotexts = ax1.pie(
            canal_counts, labels=canal_counts.index, autopct='%1.1f%%',
            colors=colors, startangle=140, wedgeprops={'edgecolor': 'white'}
        )
        centre_circle = plt.Circle((0, 0), 0.30, fc='white')
        ax1.add_artist(centre_circle)
        plt.setp(autotexts, size=11, color="black")
        st.pyplot(fig1)

    with col_b:
        # Gráfico 2: Barra Horizontal por CD
        st.write("#### Venta Neta por Centro de Distribución")
        cd_sales = df_filtered.groupby('centro_dist')['venta_neta'].sum().sort_values(ascending=False).reset_index()
        fig2, ax2 = plt.subplots(figsize=(10, 7.5)) # Ajuste de tamaño para Streamlit
        sns.barplot(data=cd_sales, x='venta_neta', y='centro_dist', hue='centro_dist', palette='viridis', legend=False, ax=ax2)
        ax2.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'{x/1e6:.1f}M'))
        ax2.set_xlabel("Venta Neta Acumulada ($)")
        ax2.set_ylabel("Centro de Distribución")
        st.pyplot(fig2)

    # Fila 2: Evolución Temporal (Line Chart) - Ancho completo
    st.write("#### Evolución Temporal de Unidades Vendidas")
    temporal_sales = df_filtered.groupby('fecha_compra')['unidades'].sum().reset_index()
    fig3, ax3 = plt.subplots(figsize=(14, 5))
    sns.lineplot(data=temporal_sales, x='fecha_compra', y='unidades', marker='o', color='#21918c', ax=ax3)
    ax3.set_xlabel("Fecha de Compra")
    ax3.set_ylabel("Total Unidades")
    ax3.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45)
    st.pyplot(fig3)

# --- REFLEXIÓN FINAL ---
st.divider()
with st.expander("Ver Reflexión Académica"):
    st.markdown("""
    **¿Qué interactividad agregamos y por qué mejora la exploración?**
    1. **Filtros Dinámicos de Canal y Precio:** Permiten al usuario realizar "Data Drill-down" instantáneo, observando cómo cambia la tendencia temporal y la carga de los Centros de Distribución según el segmento de venta.
    2. **Mapa Híbrido (HeatMap + Choropleth):** Resuelve el problema de la visualización de puntos masivos mediante densidad de calor, manteniendo el contexto administrativo de las comunas.
    3. **Sincronización de Componentes:** Al estar integrados en Streamlit, un solo filtro actualiza tanto el mapa geoespacial como los gráficos estadísticos derivados del Notebook, permitiendo una narrativa de datos coherente.
    """)