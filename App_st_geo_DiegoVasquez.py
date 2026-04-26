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

# Carga de datos
@st.cache_data
def load_data():
    nombre_archivo = "dataset_tarea_ind.xlsx"
    df = pd.read_excel(nombre_archivo, engine='openpyxl')
    
    # Limpieza de l data set
    cols_a_limpiar = ['venta_neta', 'lat', 'lng', 'kms_dist', 'lat_cd', 'lng_cd', 'unidades']
    for col in cols_a_limpiar:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
    
    
    df['fecha_compra'] = pd.to_datetime(df['fecha_compra'], dayfirst=True)
    
     
    df = df.dropna(subset=['lat', 'lng'])
    
    
    df['comuna'] = df['comuna'].str.upper().str.strip()
    return df





@st.cache_data
def load_geojson():
    geo = gpd.read_file("comunas_metropolitana-1.geojson")
    geo['name'] = geo['name'].str.upper().str.strip()
    return geo

 
try:
    df = load_data()
    geo_data = load_geojson()
except Exception as e:
    st.error(f"Error al cargar archivos: {e}")
    st.stop()

# Filtros 
st.sidebar.header(" Filtros")

 
if st.sidebar.button("🔄 Resetear Filtros"):
    st.rerun()



 
canal_selected = st.sidebar.multiselect(
    "Canal de Venta:",
    options=sorted(df['canal'].unique()),
    default=df['canal'].unique()
)

 
cd_selected = st.sidebar.multiselect(
    "Centro de Distribución (CD):",
    options=sorted(df['centro_dist'].unique()),
    default=df['centro_dist'].unique()
)

 
comuna_selected = st.sidebar.multiselect(
    "Comunas de Entrega:",
    options=sorted(df['comuna'].unique()),
    default=df['comuna'].unique()
)

 
min_v = int(df['venta_neta'].min())
max_v = int(df['venta_neta'].max())
rango_venta = st.sidebar.slider("Valor de Venta Neta ($):", min_v, max_v, (min_v, max_v))

 
fecha_min_data = df['fecha_compra'].min().date()
fecha_max_data = df['fecha_compra'].max().date()

st.sidebar.subheader("Periodo de Análisis")
fecha_rango = st.sidebar.date_input(
    "Seleccione el periodo:",
    value=(fecha_min_data, fecha_max_data),
    min_value=fecha_min_data,
    max_value=fecha_max_data
)

 
mask = (
    (df['canal'].isin(canal_selected)) &
    (df['centro_dist'].isin(cd_selected)) &
    (df['comuna'].isin(comuna_selected)) &
    (df['venta_neta'] >= rango_venta[0]) &
    (df['venta_neta'] <= rango_venta[1])
)

 
if isinstance(fecha_rango, tuple) and len(fecha_rango) == 2:
    mask = mask & (df['fecha_compra'].dt.date >= fecha_rango[0]) & (df['fecha_compra'].dt.date <= fecha_rango[1])

df_filtered = df[mask]



#  CUERPO  
st.title(" Dashboard de Visualización de Datos GeoEspaciales")
st.markdown(f"**Alumno:** Diego Vásquez Orellana")

# indicadores principales 
if not df_filtered.empty:
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Venta Total Filtrada", f"$ {df_filtered['venta_neta'].sum():,.0f}")
    with k2:
        st.metric("Total Pedidos", f"{len(df_filtered):,}")
    with k3:
        st.metric("Ticket Promedio", f"$ {df_filtered['venta_neta'].mean():,.0f}")
else:
    st.warning(" No hay datos para los filtros seleccionados.")


tab1, tab2 = st.tabs([" Visualización Geoespacial", " Análisis Estadístico"])

with tab1:
    st.subheader("Explorador Geográfico")
    tipo_mapa = st.selectbox(
        "Seleccione Capa de Análisis:",
        ["1.- Mapa Red Logística (CDs y Entregas)", 
         "2.- Mapa de Calor: Densidad de Pedidos", 
         "3.- Mapa de Calor: Intensidad Económica (Ventas)", 
         "4.- Mapa Coropleta: Venta Neta por Comuna",
         "5.- Análisis Combinado: Ventas + Densidad" ]
    )
    
    m = folium.Map(location=[-33.45694, -70.64827], zoom_start=11,min_zoom=10,
    max_zoom=16, tiles='cartodbpositron')

    if not df_filtered.empty:

        if tipo_mapa == "1.- Mapa Red Logística (CDs y Entregas)":

     
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])
            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='red', icon='home', prefix='fa')
                ).add_to(m)

            
            muestra = df_filtered.sample(n=min(1000, len(df_filtered)), random_state=42)
            
            marker_cluster = MarkerCluster(name="Entregas a Clientes").add_to(m)

            for _, row in muestra.iterrows():
                folium.CircleMarker(
                    location=[row['lat'], row['lng']],
                    radius=3,
                    color='blue',
                    fill=True,
                    fill_color='blue',
                    fill_opacity=0.6,
                    popup=f"<b>Venta:</b> ${row['venta_neta']:.0f}<br><b>Canal:</b> {row['canal']}"
                ).add_to(marker_cluster)
                
            st_folium(m, width=1000, height=600)
                
                
                
                

        elif tipo_mapa == "2.- Mapa de Calor: Densidad de Pedidos":

            # 🔹 1. Crear mapa base (esto a veces falta en el .py)
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=11,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )

            # 🔹 2. HeatMap (igual que tu notebook)
            data_cantidad = df_filtered[['lat', 'lng']].dropna().values.tolist()

            HeatMap(
                data_cantidad,
                radius=12,
                blur=8,
                min_opacity=0.4,
                gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}
            ).add_to(m)

            # 🔹 3. GeoJson (comunas)
            geo_data['name'] = geo_data['name'].str.upper().str.strip()

            folium.GeoJson(
                geo_data,
                style_function=lambda x: {
                    'fillColor': 'transparent',
                    'color': 'gray',
                    'weight': 1
                },
                highlight_function=lambda x: {
                    'fillColor': 'yellow',
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name'],
                    aliases=['Comuna:']
                )
            ).add_to(m)

            # 🔹 4. Centros de distribución (CDs)
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='black', icon='home', prefix='fa')
                ).add_to(m)

            # 🔹 5. Mostrar en Streamlit
            st_folium(m, width=1000, height=600)
        
        
        
        
        
        elif tipo_mapa == "3.- Mapa de Calor: Intensidad Económica (Ventas)":

            # 🔹 1. Crear mapa base (clave en Streamlit)
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=11,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )

            # 🔹 2. Normalización segura (evita división por 0)
            max_val = df_filtered['venta_neta'].max()
            max_val = max_val if max_val > 0 else 1

            df_filtered = df_filtered.copy()  # ⚠️ evita warning de pandas
            df_filtered['venta_norm'] = df_filtered['venta_neta'] / max_val

            # 🔥 3. Heatmap ponderado (igual que notebook)
            data_venta = df_filtered[['lat', 'lng', 'venta_norm']].dropna().values.tolist()

            HeatMap(
                data_venta,
                radius=15,
                blur=10,
                min_opacity=0.5
            ).add_to(m)

            # 🔴 4. Centros de distribución
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='black', icon='home', prefix='fa')
                ).add_to(m)

            # 🟢 5. GeoJson (hover de comunas)
            geo_data['name'] = geo_data['name'].str.upper().str.strip()

            folium.GeoJson(
                geo_data,
                style_function=lambda x: {
                    'fillColor': 'transparent',
                    'color': 'gray',
                    'weight': 1
                },
                highlight_function=lambda x: {
                    'fillColor': 'yellow',
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['name'],
                    aliases=['Comuna:']
                )
            ).add_to(m)

            # 🔹 6. Mostrar en Streamlit
            st_folium(m, width=1000, height=600)
    
    
    
    
    

        elif tipo_mapa == "4.- Mapa Coropleta: Venta Neta por Comuna":

            # 🔹 1. Crear mapa base (clave en Streamlit)
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=10,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )

            # 🔹 2. Agrupación de ventas por comuna
            ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
            ventas_comuna['comuna'] = ventas_comuna['comuna'].str.upper().str.strip()

            # 🔹 3. Normalizar nombres en geo_data (MUY IMPORTANTE)
            geo_data['name'] = geo_data['name'].str.upper().str.strip()

            # 🔹 4. Coropleta (igual a tu notebook)
            choropleth = folium.Choropleth(
                geo_data=geo_data,
                name="choropleth",
                data=ventas_comuna,
                columns=["comuna", "venta_neta"],
                key_on="feature.properties.name",
                fill_color="YlGnBu",
                fill_opacity=0.7,
                line_opacity=0.2,
                legend_name="Venta Neta Total por Comuna ($)",
                highlight=True,
                bins=3  # 🔥 mejora visual de la leyenda
            ).add_to(m)

            # 🔴 5. Centros de distribución
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='red', icon='home', prefix='fa')
                ).add_to(m)

            # 🔹 6. Tooltip con formato moneda (igual que notebook)
            ventas_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()

            for feature in choropleth.geojson.data['features']:
                nom_comuna = feature['properties']['name']
                venta = ventas_dict.get(nom_comuna, 0)
                feature['properties']['Venta_Total_Fmt'] = f"$ {venta:,.0f}"

            choropleth.geojson.add_child(
                folium.features.GeoJsonTooltip(
                    fields=['name', 'Venta_Total_Fmt'],
                    aliases=['Comuna:', 'Ventas Totales:'],
                    localize=True
                )
            )

            # 🔹 7. Mostrar en Streamlit
            st_folium(m, width=1000, height=600)
            
            
            
            
            

        elif tipo_mapa == "5.- Análisis Combinado: Ventas + Densidad":

            # 🔹 1. Crear mapa base (faltaba en tu bloque)
            m = folium.Map(
                location=[-33.45694, -70.64827],
                zoom_start=11,
                min_zoom=10,
                max_zoom=16,
                tiles='cartodbpositron'
            )

            # 🔹 2. Preparación de datos
            ventas_comuna = df_filtered.groupby('comuna')['venta_neta'].sum().reset_index()
            ventas_comuna['comuna'] = ventas_comuna['comuna'].str.upper().str.strip()
            ventas_comuna['venta_mm'] = ventas_comuna['venta_neta'] / 1_000_000

            geo_data['name'] = geo_data['name'].str.upper().str.strip()

            # 🔹 3. Coropleta (capa base)
            choropleth = folium.Choropleth(
                geo_data=geo_data,
                data=ventas_comuna,
                columns=["comuna", "venta_mm"],
                key_on="feature.properties.name",
                fill_color="YlGn",
                fill_opacity=0.4,
                line_opacity=0.2,
                legend_name="Venta Neta por Comuna (MM$)",
                highlight=True
            ).add_to(m)

            # 🔴 4. Centros de distribución
            cds_unicos = df_filtered.drop_duplicates(subset=['centro_dist'])

            for _, row in cds_unicos.iterrows():
                folium.Marker(
                    location=[row['lat_cd'], row['lng_cd']],
                    popup=f"<b>CD:</b> {row['centro_dist']}<br><b>Comuna:</b> {row['comuna']}",
                    tooltip=row['centro_dist'],
                    icon=folium.Icon(color='red', icon='home', prefix='fa')  # 🔴 igual que notebook
                ).add_to(m)

            # 🔹 5. Tooltip enriquecido (igual que notebook)
            ventas_dict = ventas_comuna.set_index('comuna')['venta_neta'].to_dict()

            for feature in choropleth.geojson.data['features']:
                nom = feature['properties']['name']
                venta = ventas_dict.get(nom, 0)
                feature['properties']['info_tooltip'] = f"Comuna: {nom} | Ventas: $ {venta:,.0f}"

            choropleth.geojson.add_child(
                folium.features.GeoJsonTooltip(
                    fields=['info_tooltip'],
                    labels=False,
                    sticky=True
                )
            )

            # 🔥 6. Heatmap (capa superior)
            data_puntos = df_filtered[['lat', 'lng']].dropna().values.tolist()

            HeatMap(
                data_puntos,
                radius=12,
                blur=18,
                min_opacity=0.3,
                gradient={0.4: 'blue', 0.6: 'purple', 1: 'red'},
                name="Densidad de Pedidos (Calor)"  # 🔥 importante para LayerControl
            ).add_to(m)

            # 🔹 7. Control de capas (clave en este mapa)
            folium.LayerControl().add_to(m)

            # 🔹 8. Mostrar en Streamlit
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
            sns.barplot(x=cd_sales.values, y=cd_sales.index, palette='viridis', hue=cd_sales.index, legend=False, ax=ax2)
            ax2.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'{x/1e6:.1f}M'))
            st.pyplot(fig2)

        st.write("#### Evolución Temporal de Unidades")
        temporal = df_filtered.groupby('fecha_compra')['unidades'].sum().reset_index()
        fig3, ax3 = plt.subplots(figsize=(12, 4))
        sns.lineplot(data=temporal, x='fecha_compra', y='unidades', marker='o', color='#21918c', ax=ax3)
        plt.xticks(rotation=45)
        st.pyplot(fig3)
    else:
        st.info("Utilice los filtros laterales para visualizar el análisis estadístico.")

# --- REFLEXIÓN ---
st.divider()
with st.expander(" Reflexión sobre la visualización"):
    st.markdown("""
    **Análisis de Impacto de Filtros Avanzados:**
    1. **Filtro Temporal:** Permite identificar picos de demanda entre enero y abril de 2025, optimizando la planificación de inventario.
    2. **Filtros Geo-Logísticos:** Al combinar el filtro de Comuna y CD, la empresa puede detectar si un Centro de Distribución específico está subutilizado o si la demanda de una comuna está siendo atendida por un CD ineficiente (lejano).
    3. **Rendimiento:** El uso de `st.cache_data` y el muestreo de 1000 puntos asegura que el dashboard sea rápido incluso con miles de registros.
    """)
