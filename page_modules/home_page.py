import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from database import get_db_connection, test_db_connection, execute_query
import toml
import os
import sys

# Hozzáadja a szülő könyvtárat a path-hoz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_call import fetch_co2_emission_data

def show_home_page():
    with open('styles.css', 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    st.markdown(f"""
    <style>
    {css_content}
    </style>
    """, unsafe_allow_html=True)
    
    st.write("# Főoldal")
    
    # Database connection test
    if st.button("Adatbázis teszt"):
        if test_db_connection():
            st.success("Sikeres csatlakozás")
        else:
            st.error("Sikertelen csatlakozás")

    st.write("---")
    
    # Adatbázis táblák kiválasztása
    st.write("## Adatbázis lekérdezés")
    
    # Session state inicializálása
    if "selected_table" not in st.session_state:
        st.session_state.selected_table = "dfv_smart_db"
        st.session_state.table_display_name = "Oksomérő"
    
    selected_table = st.session_state.selected_table
    table_display_name = st.session_state.table_display_name
    
    # Táblák kiválasztása gombokkal
    col1, col2 = st.columns(2)
    
    with col1:
        # Oksomérő gomb - narancssárga ha kiválasztott
        if selected_table == "dfv_smart_db":
            if st.button("Oksomérő", use_container_width=True, type="primary"):
                st.session_state.selected_table = "dfv_smart_db"
                st.session_state.table_display_name = "Oksomérő"
                st.rerun()
        else:
            if st.button("Oksomérő", use_container_width=True, type="secondary"):
                st.session_state.selected_table = "dfv_smart_db"
                st.session_state.table_display_name = "Oksomérő"
                st.rerun()
    
    with col2:
        # Termosztátos mérő gomb - narancssárga ha kiválasztott
        if selected_table == "dfv_termosztat_db":
            if st.button("Termosztátos mérő", use_container_width=True, type="primary"):
                st.session_state.selected_table = "dfv_termosztat_db"
                st.session_state.table_display_name = "Termosztátos mérő"
                st.rerun()
        else:
            if st.button("Termosztátos mérő", use_container_width=True, type="secondary"):
                st.session_state.selected_table = "dfv_termosztat_db"
                st.session_state.table_display_name = "Termosztátos mérő"
                st.rerun()
    

    
    # Elemek száma beállítása - globális érték minden táblához
    col1, col2 = st.columns([1, 2])
    
    # Globális page size inicializálása
    if "global_page_size" not in st.session_state:
        st.session_state.global_page_size = 5
    
    with col1:
        # Jelenlegi globális page_size értékének indexe
        current_page_size = st.session_state.global_page_size
        page_size_options = [5, 15, 25]
        try:
            current_index = page_size_options.index(current_page_size)
        except ValueError:
            current_index = 0
        
        page_size = st.selectbox(
            "Elemek száma:",
            page_size_options,
            index=current_index,
            key="global_page_size_selector"
        )
        
        # Globális page size frissítése session state-ben
        st.session_state.global_page_size = page_size
    
    with col2:
        st.write("")
    
    # Session state inicializálása a lapozáshoz
    if f"offset_{selected_table}" not in st.session_state:
        st.session_state[f"offset_{selected_table}"] = 0
    
    # Session state inicializálása a diagram generáláshoz
    if "chart_generated" not in st.session_state:
        st.session_state.chart_generated = False
    
    # Adatok lekérdezése
    try:
        # Globális page size lekérése session state-ből
        current_page_size = st.session_state.global_page_size
        query = f"SELECT * FROM {selected_table} LIMIT {current_page_size} OFFSET {st.session_state[f'offset_{selected_table}']}"
        result = execute_query(query)
        
        if result:
            # DataFrame létrehozása
            df = pd.DataFrame(result)
            st.write(f"### {table_display_name} adatai")
            
            # Oszlopnevek definiálása
            column_names = [
                "Dátum", "Idő", "Harmatpont (°C)", "Hőmérséklet (°C)", 
                "Áramerősség (A)", "Feszültség (V)", "Teljesítmény (W)", 
                "Relatív páratartalom (%)", "Külső páratartalom (%)", "Külső hőmérséklet (°C)"
            ]
            
            # Az első oszlop (0. index) kihagyása, de az index oszlop megjelenítése
            if len(df.columns) > 1:
                df_display = df.iloc[:, 1:]  # Az első oszlop kihagyása
                # Oszlopnevek beállítása (csak annyi, amennyi van)
                available_columns = min(len(column_names), len(df_display.columns))
                df_display.columns = column_names[:available_columns]
            else:
                df_display = df
                if len(df_display.columns) > 0:
                    df_display.columns = column_names[:len(df_display.columns)]
            
            # Numerikus oszlopok kerekítése 2 tizedesjegyre (3. oszloptól kezdve)
            for i, col in enumerate(df_display.columns):
                if i >= 2:

                    try:
                        df_display[col] = pd.to_numeric(df_display[col], errors='coerce')
                        if df_display[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                            df_display[col] = df_display[col].round(2)
                    except:
                        pass  # Ha nem lehet konvertálni, hagyja változatlanul
            
            st.dataframe(df_display, use_container_width=True, hide_index=False)
            

            
            
            col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 0.2, 0.2, 0.2, 0.2, 0.1, 0.3])
            
            with col1:
                st.write("")  
            
            with col2:
                if st.button("⏮️"):
                    st.session_state[f"offset_{selected_table}"] = 0
                    st.rerun()
            
            with col3:
                if st.button("⬅️"):
                    current_page_size = st.session_state.global_page_size
                    if st.session_state[f"offset_{selected_table}"] >= current_page_size:
                        st.session_state[f"offset_{selected_table}"] -= current_page_size
                        st.rerun()
            
            with col4:
                #Következő oldalon található-e még adat
                current_page_size = st.session_state.global_page_size
                current_offset = st.session_state[f"offset_{selected_table}"]
                
                
                try:
                    count_query = f"SELECT COUNT(*) FROM {selected_table}"
                    total_count = execute_query(count_query)[0][0]
                    
                  
                    next_offset = current_offset + current_page_size
                    has_next_page = next_offset < total_count
                    
                    if st.button("➡️", disabled=not has_next_page):
                        st.session_state[f"offset_{selected_table}"] = next_offset
                        st.rerun()
                except Exception as e:
                    if st.button("➡️"):
                        st.session_state[f"offset_{selected_table}"] += current_page_size
                        st.rerun()
            
            with col5:
                #Utolsó oldalon van-e még adat
                current_page_size = st.session_state.global_page_size
                current_offset = st.session_state[f"offset_{selected_table}"]
                
                try:
                    count_query = f"SELECT COUNT(*) FROM {selected_table}"
                    total_count = execute_query(count_query)[0][0]
                    
                    # Utolsó oldal offset
                    last_page_offset = (total_count // current_page_size) * current_page_size
                    
                    
                    is_on_last_page = current_offset >= last_page_offset
                    
                    if st.button("⏭️", disabled=is_on_last_page):
                        st.session_state[f"offset_{selected_table}"] = last_page_offset
                        st.rerun()
                except Exception as e:
                    st.error(f"Hiba az utolsó oldal kiszámításakor: {e}")
                    
                    if st.button("⏭️"):
                        st.session_state[f"offset_{selected_table}"] = 1000
                        st.rerun()
            
            with col6:
                st.write("")  
            
            with col7:
                # Jelenlegi oldal és összes oldal információ
                current_page_size = st.session_state.global_page_size
                current_page = (st.session_state[f"offset_{selected_table}"] // current_page_size) + 1
            
                # Összes oldal számának kiszámítása
                try:
                    count_query = f"SELECT COUNT(*) FROM {selected_table}"
                    total_count = execute_query(count_query)[0][0]
                    total_pages = (total_count + current_page_size - 1) // current_page_size 
                    st.write(f" **Oldal:** {current_page} / {total_pages}")
                except Exception as e:
                    st.write(f"**Oldal:** {current_page}")
            
        else:
            st.warning("Nincs adat a kiválasztott táblában.")
            
    except Exception as e:
        st.error(f"Adatbázishiba: {e}")
        st.write("Ellenőrizd, hogy a kiválasztott tábla létezik-e az adatbázisban.")
    
    # Plot canvas hozzáadása
    st.write("---")
    st.write("##  Historikus adatok vizuális lekérése")
    
    # Plot canvas mindig megjelenik
    if 'df' in locals() and df is not None and not df.empty:
        # Oszlopnevek kiválasztása
        numeric_columns = []
        for i, col in enumerate(df_display.columns):
            if i >= 2:
                try:
                    pd.to_numeric(df_display[col], errors='coerce')
                    numeric_columns.append(col)
                except:
                    pass
        
        if numeric_columns:
            col1, col2 = st.columns(2)
            
            with col1:
                selected_column = st.selectbox(
                    "Válassz oszlopot a diagramhoz:",
                    numeric_columns,
                    key="chart_column_selector"
                )
            
            with col2:
                time_interval = st.selectbox(
                    "Időintervallum:",
                    ["1 óra", "3 óra", "12 óra", "1 nap", "3 nap","7 nap", "Egyedi időtartam"],
                    key="time_interval_selector"
                )
            
            
            custom_start_time = None
            custom_end_time = None
            
            if time_interval == "Egyedi időtartam":
                col1, col2 = st.columns(2)
                with col1:
                    custom_start_time = st.date_input("Kezdő dátum:", key="custom_start_date")
                with col2:
                    custom_end_time = st.date_input("Befejező dátum:", key="custom_end_date")
            
            # Automatikus diagram generálás oszlop vagy időintervallum váltáskor
            # Session state inicializálása a diagram adatokhoz
            if "chart_data_cache" not in st.session_state:
                st.session_state.chart_data_cache = {}
            
            # Cache kulcs létrehozása a jelenlegi beállítások alapján
            cache_key = f"{selected_table}_{selected_column}_{time_interval}"
            if time_interval == "Egyedi időtartam":
                cache_key += f"_{custom_start_time}_{custom_end_time}"
            
            # Ha van cache-elt adat és nem változtak a beállítások, azt használjuk
            if cache_key in st.session_state.chart_data_cache:
                chart_data = st.session_state.chart_data_cache[cache_key]
            else:
                # Új adatok lekérdezése
                try:
                    # Időintervallumok megadása
                    last_data_time = datetime(2025, 8, 21, 23, 45, 0) 
                    first_data_time = datetime(2024, 8, 19, 8, 0, 0)
                    
                    if time_interval == "1 óra":
                        start_time = last_data_time - timedelta(hours=1)
                    elif time_interval == "3 óra":
                        start_time = last_data_time - timedelta(hours=3)
                    elif time_interval == "12 óra":
                        start_time = last_data_time - timedelta(hours=12)
                    elif time_interval == "1 nap":
                        start_time = last_data_time - timedelta(days=1)
                    elif time_interval == "3 nap":
                        start_time = last_data_time - timedelta(days=3)
                    elif time_interval == "7 nap":
                        start_time = last_data_time - timedelta(days=7)
                    elif time_interval == "Egyedi időtartam":
                        if custom_start_time and custom_end_time:
                            start_time = datetime.combine(custom_start_time, datetime.min.time())
                            end_time = datetime.combine(custom_end_time, datetime.max.time())
                        else:
                            st.error("Válassz ki kezdő és befejező dátumot!")
                            chart_data = None
                        if chart_data is None:
                            st.stop()
                    else:
                        start_time = last_data_time - timedelta(hours=1)
                    
                    if start_time < first_data_time:
                        start_time = first_data_time
                    
                    # Adatok lekérdezése az időintervallum alapján
                    if time_interval == "Egyedi időtartam" and custom_start_time and custom_end_time:
                        query = f"""
                        SELECT * FROM {selected_table} 
                        WHERE DATE(date) BETWEEN '{start_time.strftime('%Y-%m-%d')}' AND '{end_time.strftime('%Y-%m-%d')}'
                        ORDER BY date, time
                        """
                    else:
                        query = f"""
                        SELECT * FROM {selected_table} 
                        WHERE CONCAT(date, ' ', time) <= '{last_data_time.strftime('%Y-%m-%d %H:%M:%S')}'
                        AND CONCAT(date, ' ', time) >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
                        ORDER BY date, time
                        """
                    
                    chart_data = execute_query(query)
                    
                    # Cache-eljük az adatokat
                    st.session_state.chart_data_cache[cache_key] = chart_data
                    
                except Exception as e:
                    st.error(f"Hiba a diagram generálásakor: {e}")
                    chart_data = None
            
            # Diagram megjelenítése (cache-ből vagy új adatokból)
            if chart_data:
                # DataFrame létrehozása a diagramhoz
                chart_df = pd.DataFrame(chart_data)
                
                # Oszlopnevek beállítása
                chart_df.columns = ["ID", "Dátum", "Idő", "Harmatpont (°C)", "Hőmérséklet (°C)", 
                                  "Áramerősség (A)", "Feszültség (V)", "Teljesítmény (W)", 
                                  "Relatív páratartalom (%)", "Külső páratartalom (%)", "Külső hőmérséklet (°C)"]
                
                # Dátum-idő oszlop kombinálása
                chart_df['Dátum_Idő'] = pd.to_datetime(chart_df['Dátum'].astype(str) + ' ' + chart_df['Idő'].astype(str))
                
                # Kiválasztott oszlop adatainak előkészítése
                chart_df[selected_column] = pd.to_numeric(chart_df[selected_column], errors='coerce')
                
                # Vonaldiagram létrehozása
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=chart_df['Dátum_Idő'],
                    y=chart_df[selected_column],
                    mode='lines+markers',
                    name=selected_column,
                    line=dict(width=2),
                    marker=dict(size=4)
                ))
                
                fig.update_layout(
                    title=f"{selected_column} változása az időben",
                    xaxis_title="Dátum és idő",
                    yaxis_title=selected_column,
                    hovermode='x unified',
                    template="plotly_white"
                )
                
                # X tengely formázása
                fig.update_xaxes(
                    tickformat="%m-%d %H:%M",
                    tickangle=45
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.session_state.chart_generated = True
                
                # Statisztikák megjelenítése
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Minimális érték", f"{chart_df[selected_column].min():.2f}")
                with col2:
                    st.metric("Maximális érték", f"{chart_df[selected_column].max():.2f}")
                with col3:
                    st.metric("Átlag", f"{chart_df[selected_column].mean():.2f}")
                with col4:
                    st.metric("Mérések száma", len(chart_df))
                    
            else:
                st.warning("Nincs adat a kiválasztott időintervallumban.")
        else:
            st.info("Nincs numerikus oszlop a diagramokhoz.")
    else:
        st.info("Először válassz ki egy táblát a diagramok megjelenítéséhez.")
    
    # CO2 kibocsátási adatok lekérdezése
    st.write("---")
    st.write("## CO2 Kibocsátási Adatok")
    
    days_to_show = 10
    
    # API kulcs betöltése a config.toml fájlból
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.toml')
        config = toml.load(config_path)
        api_key = config['api']['electricity_maps_token']
    except Exception as e:
        st.error(f"Hiányzik a config.toml fájl vagy az API kulcs. Hiba: {e}")
        api_key = None
    
    # Session state inicializálása
    if 'co2_cached_days' not in st.session_state:
        st.session_state.co2_cached_days = 10
    
    # Automatikusan lekérdezi, ha nincsenek cached adatok
    auto_refresh = ('co2_hourly_dataframe' not in st.session_state)
    
    if auto_refresh and api_key:
        with st.spinner("Adatok lekérése folyamatban..."):
            co2_hourly_df, co2_hourly_with_power, daily_co2_df = fetch_co2_emission_data(days_to_show, api_key)
            
            if co2_hourly_df is not None:
                # Adatok cache-elése
                st.session_state['co2_hourly_dataframe'] = co2_hourly_df
                st.session_state['co2_cached_days'] = days_to_show
                
                if co2_hourly_with_power is not None and daily_co2_df is not None:
                    st.session_state['co2_hourly_with_power'] = co2_hourly_with_power
                    st.session_state['co2_daily_dataframe'] = daily_co2_df
                    st.success(f"Sikeresen lekérve {len(co2_hourly_df)} órás CO2 adatpont és {len(daily_co2_df)} napi energia adat!")
                else:
                    st.warning("Nincs energiafogyasztási adat az adatbázisban az időszakra.")
    
    
    if 'co2_hourly_dataframe' in st.session_state and st.session_state['co2_hourly_dataframe'] is not None:
        co2_hourly_df = st.session_state['co2_hourly_dataframe']
        
        # Órás CO2 kibocsátás megjelenítése
        if 'co2_hourly_with_power' in st.session_state and st.session_state['co2_hourly_with_power'] is not None:
            co2_hourly_with_power = st.session_state['co2_hourly_with_power']
            
            st.write("### Tényleges Órás CO2 Kibocsátás")
            
            # Diagram 
            fig2 = go.Figure()
            
            fig2.add_trace(go.Scatter(
                x=co2_hourly_with_power['Dátum és idő'],
                y=co2_hourly_with_power['Óras CO2 (kg)'],
                mode='lines+markers',
                name='Órás CO2 Kibocsátás',
                line=dict(color='#4ECDC4', width=2),
                marker=dict(size=4)
            ))
            
            fig2.update_layout(
                title="Órás CO2 Kibocsátás (Villamosenergia fogyasztás alapján)",
                xaxis_title="Dátum és idő",
                yaxis_title="CO2 Kibocsátás (kg)",
                hovermode='x unified',
                template="plotly_white",
                height=500
            )
            
            fig2.update_xaxes(
                tickformat="%m-%d %H:%M",
                tickangle=45
            )
            
            st.plotly_chart(fig2, use_container_width=True)
            
            # Napi adatok - táblázatba szedve
            if 'co2_daily_dataframe' in st.session_state and st.session_state['co2_daily_dataframe'] is not None:
                daily_co2_df = st.session_state['co2_daily_dataframe']
                
                st.write("---")
                st.write("### Napi CO2 Kibocsátás Összesített Adatai")
                display_daily_df = daily_co2_df[['Dátum', 'Napi energia (kWh)', 'Átlag CO2 (g CO2/kWh)', 'Napi CO2 (kg)']].copy()
                display_daily_df.columns = ['Dátum', 'Energia (kWh)', 'Átlagos CO2 Intenzitás (g/kWh)', 'Napi CO2 Kibocsátás (kg)']
                st.dataframe(display_daily_df, use_container_width=True)
            
            # Statisztikák (órás bontásba)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_co2_kg = co2_hourly_with_power['Óras CO2 (kg)'].sum()
                st.metric("Összes CO2", f"{total_co2_kg:.2f} kg")
            with col2:
                avg_hourly_co2_kg = co2_hourly_with_power['Óras CO2 (kg)'].mean()
                st.metric("Átlagos óras CO2", f"{avg_hourly_co2_kg:.4f} kg")
            with col3:
                max_hourly_co2_kg = co2_hourly_with_power['Óras CO2 (kg)'].max()
                st.metric("Maximum óras CO2", f"{max_hourly_co2_kg:.4f} kg")
        
        # Napi összesített adatok megjelenítése
        elif 'co2_daily_dataframe' in st.session_state and st.session_state['co2_daily_dataframe'] is not None:
            daily_co2_df = st.session_state['co2_daily_dataframe']
            
            st.write("### Tényleges Napi CO2 Kibocsátás")
            
            # Diagram
            fig2 = go.Figure()
            
            fig2.add_trace(go.Scatter(
                x=daily_co2_df['Dátum_datetime'],
                y=daily_co2_df['Napi CO2 (kg)'],
                mode='lines+markers',
                name='Napi CO2 Kibocsátás',
                line=dict(color='#4ECDC4', width=3),
                marker=dict(size=6)
            ))
            
            fig2.update_layout(
                title="Napi CO2 Kibocsátás (Villamosenergia fogyasztás alapján)",
                xaxis_title="Dátum",
                yaxis_title="CO2 Kibocsátás (kg)",
                hovermode='x unified',
                template="plotly_white",
                height=500
            )
            
            fig2.update_xaxes(
                tickformat="%m-%d",
                tickangle=45
            )
            
            st.plotly_chart(fig2, use_container_width=True)
            
            # Statisztikák
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_co2_kg = daily_co2_df['Napi CO2 (kg)'].sum()
                st.metric("Összes CO2", f"{total_co2_kg:.2f} kg")
            with col2:
                avg_daily_co2_kg = daily_co2_df['Napi CO2 (kg)'].mean()
                st.metric("Átlagos napi CO2", f"{avg_daily_co2_kg:.2f} kg")
            with col3:
                max_daily_co2_kg = daily_co2_df['Napi CO2 (kg)'].max()
                st.metric("Maximum napi CO2", f"{max_daily_co2_kg:.2f} kg")
            with col4:
                st.metric("Napok száma", len(daily_co2_df))
            
            # Táblázatos megjelenítés
            st.write("### Részletes napi adatok")
            display_df = daily_co2_df[['Dátum', 'Napi energia (kWh)', 'Átlag CO2 (g CO2/kWh)', 'Napi CO2 (kg)']].copy()
            display_df.columns = ['Dátum', 'Energia (kWh)', 'Átlagos CO2 Intenzitás (g/kWh)', 'Napi CO2 (kg)']
            st.dataframe(display_df, use_container_width=True)