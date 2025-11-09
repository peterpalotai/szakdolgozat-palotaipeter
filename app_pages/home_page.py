import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, time
from app_services.database import get_db_connection, test_db_connection, execute_query
import os
import sys

# Hozzáadja a szülő könyvtárat a path-hoz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_services.api_call_CO2 import fetch_co2_emission_data

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
        st.session_state.table_display_name = "Oksovezérlő"
        st.session_state.prev_selected_table = None
    
    selected_table = st.session_state.selected_table
    table_display_name = st.session_state.table_display_name
    
    # Ha váltottunk táblát, töröljük a CO2 cache-t és diagram cache-t
    if "prev_selected_table" in st.session_state and st.session_state.prev_selected_table != selected_table:
        # Előző táblához tartozó diagram cache-bejegyzések törlése
        if "chart_data_cache" in st.session_state:
            keys_to_delete = [key for key in st.session_state.chart_data_cache.keys() 
                             if key.startswith(f"{st.session_state.prev_selected_table}_")]
            for key in keys_to_delete:
                del st.session_state.chart_data_cache[key]
        
        # CO2 cache törlése, hogy újragenerálódjanak az adatok
        if 'co2_hourly_dataframe' in st.session_state:
            del st.session_state['co2_hourly_dataframe']
        if 'co2_hourly_with_power' in st.session_state:
            del st.session_state['co2_hourly_with_power']
        if 'co2_daily_dataframe' in st.session_state:
            del st.session_state['co2_daily_dataframe']
        if 'co2_cached_days' in st.session_state:
            del st.session_state['co2_cached_days']
        
        # Offset reset az új táblához
        if f"offset_{selected_table}" in st.session_state:
            st.session_state[f"offset_{selected_table}"] = 0
        
        # Előző tábla frissítése
        st.session_state.prev_selected_table = selected_table
    
    # Táblák kiválasztása gombokkal
    col1, col2 = st.columns(2)
    
    with col1:
        # Oksovezérlő gomb - narancssárga ha kiválasztott
        if selected_table == "dfv_smart_db":
            if st.button("Oksovezérlő", use_container_width=True, type="primary"):
                # Előző tábla mentése
                st.session_state.prev_selected_table = st.session_state.selected_table
                st.session_state.selected_table = "dfv_smart_db"
                st.session_state.table_display_name = "Oksovezérlő"
                st.rerun()
        else:
            if st.button("Oksovezérlő", use_container_width=True, type="secondary"):
                # Előző tábla mentése
                st.session_state.prev_selected_table = st.session_state.selected_table
                st.session_state.selected_table = "dfv_smart_db"
                st.session_state.table_display_name = "Oksovezérlő"
                st.rerun()
    
    with col2:
        # Termosztátos vezérlő gomb - narancssárga ha kiválasztott
        if selected_table == "dfv_termosztat_db":
            if st.button("Termosztátos vezérlő", use_container_width=True, type="primary"):
                # Előző tábla mentése
                st.session_state.prev_selected_table = st.session_state.selected_table
                st.session_state.selected_table = "dfv_termosztat_db"
                st.session_state.table_display_name = "Termosztátos vezérlő"
                st.rerun()
        else:
            if st.button("Termosztátos vezérlő", use_container_width=True, type="secondary"):
                # Előző tábla mentése
                st.session_state.prev_selected_table = st.session_state.selected_table
                st.session_state.selected_table = "dfv_termosztat_db"
                st.session_state.table_display_name = "Termosztátos vezérlő"
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
        
        # Oszlopok meghatározása a táblánév alapján (feszültség oszlop kizárása)
        if selected_table == "dfv_smart_db":
            columns = "id, date, time, trend_smart_t, trend_smart_i1, trend_smart_p, trend_smart_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
        elif selected_table == "dfv_termosztat_db":
            columns = "id, date, time, trend_termosztat_t, trend_termosztat_i1, trend_termosztat_p, trend_termosztat_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
        else:
            columns = "*"  # Ha más tábla, akkor minden oszlop
        
        query = f"SELECT {columns} FROM {selected_table} LIMIT {current_page_size} OFFSET {st.session_state[f'offset_{selected_table}']}"
        result = execute_query(query)
        
        if result:
            # DataFrame létrehozása
            df = pd.DataFrame(result)
            st.write(f"### {table_display_name} adatai")
            
            # Oszlopnevek definiálása
            column_names = [
                "Dátum", "Idő", "Harmatpont (°C)", "Hőmérséklet (°C)", 
                "Áramerősség (A)", "Teljesítmény (W)", 
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
                    ["1 óra", "3 óra", "12 óra", "1 nap", "3 nap", "7 nap", "Egyéni intervallum"],
                    key="time_interval_selector"
                )
            
            # Egyéni intervallum dátumválasztók
            custom_start_date = None
            custom_end_date = None
            generate_chart = False
            if time_interval == "Egyéni intervallum":
                col3, col4 = st.columns(2)
                with col3:
                    custom_start_date = st.date_input(
                        "Kezdő dátum:",
                        value=datetime(2025, 8, 11).date(),
                        min_value=datetime(2024, 8, 19).date(),
                        max_value=datetime(2025, 8, 21).date(),
                        key="custom_start_date"
                    )
                with col4:
                    custom_end_date = st.date_input(
                        "Végdátum:",
                        value=datetime(2025, 8, 21).date(),
                        min_value=datetime(2024, 8, 19).date(),
                        max_value=datetime(2025, 8, 21).date(),
                        key="custom_end_date"
                    )
                # Egyéni intervallum esetén gomb kell a diagram generálásához
                if st.button("Diagram generálása", type="primary"):
                    generate_chart = True
            
            # Automatikus diagram generálás oszlop vagy időintervallum váltáskor (csak ha nem egyéni intervallum)
            # Session state inicializálása a diagram adatokhoz
            if "chart_data_cache" not in st.session_state:
                st.session_state.chart_data_cache = {}
            
            # Cache kulcs létrehozása a jelenlegi beállítások alapján
            if time_interval == "Egyéni intervallum" and custom_start_date and custom_end_date:
                cache_key = f"{selected_table}_{selected_column}_{time_interval}_{custom_start_date}_{custom_end_date}"
            else:
                cache_key = f"{selected_table}_{selected_column}_{time_interval}"
            
            # Egyéni intervallum esetén csak akkor generálunk, ha a gombot megnyomták
            if time_interval == "Egyéni intervallum":
                if generate_chart:
                    # Töröljük a cache-t, hogy újra lekérdezze
                    if cache_key in st.session_state.chart_data_cache:
                        del st.session_state.chart_data_cache[cache_key]
                    chart_data = None
                else:
                    # Ha van cache-elt adat, azt használjuk
                    if cache_key in st.session_state.chart_data_cache:
                        cached_data = st.session_state.chart_data_cache[cache_key]
                        if cached_data and len(cached_data) > 0:
                            chart_data = cached_data
                        else:
                            chart_data = None
                    else:
                        chart_data = None
            else:
                # Automatikus generálás a többi esetben
                # Ha van cache-elt adat és nem változtak a beállítások, azt használjuk
                if cache_key in st.session_state.chart_data_cache:
                    cached_data = st.session_state.chart_data_cache[cache_key]
                    # Csak akkor használjuk a cache-t, ha van benne adat
                    if cached_data and len(cached_data) > 0:
                        chart_data = cached_data
                    else:
                        # Ha üres volt a cache, töröljük és újra lekérdezzük
                        del st.session_state.chart_data_cache[cache_key]
                        chart_data = None
                else:
                    chart_data = None
            
            # Ha nincs cache-elt adat, lekérdezzük az új adatokat
            if chart_data is None:
                # Új adatok lekérdezése
                try:
                    # Időintervallumok megadása - először definiáljuk a globális változókat
                    last_data_time = datetime(2025, 8, 21, 23, 45, 0) 
                    first_data_time = datetime(2024, 8, 19, 8, 0, 0)
                    
                    # Időintervallumok megadása
                    if time_interval == "Egyéni intervallum":
                        # Egyéni intervallum esetén a felhasználó által megadott dátumokat használjuk
                        # A nap elejétől (00:00:00) a nap végéig (23:59:59) lekérdezzük az adatokat
                        if custom_start_date and custom_end_date:
                            # Kezdő dátum: nap eleje (00:00:00)
                            start_time = datetime.combine(custom_start_date, time(0, 0, 0))
                            # Végdátum: nap vége (23:59:59)
                            end_time = datetime.combine(custom_end_date, time(23, 59, 59))
                            # Ellenőrizzük, hogy a dátumok az adatok tartományán belül legyenek
                            if start_time < first_data_time:
                                start_time = first_data_time
                            if end_time > last_data_time:
                                end_time = last_data_time
                            # Ellenőrizzük, hogy a kezdő dátum ne legyen későbbi, mint a végdátum
                            if start_time > end_time:
                                st.error("A kezdő dátum nem lehet későbbi, mint a végdátum!")
                                chart_data = []
                        else:
                            # Ha nincs dátum megadva, alapértelmezett értékeket használunk
                            start_time = first_data_time
                            end_time = last_data_time
                    elif time_interval == "1 óra":
                        start_time = last_data_time - timedelta(hours=1)
                        end_time = last_data_time
                    elif time_interval == "3 óra":
                        start_time = last_data_time - timedelta(hours=3)
                        end_time = last_data_time
                    elif time_interval == "12 óra":
                        start_time = last_data_time - timedelta(hours=12)
                        end_time = last_data_time
                    elif time_interval == "1 nap":
                        start_time = last_data_time - timedelta(days=1)
                        end_time = last_data_time
                    elif time_interval == "3 nap":
                        start_time = last_data_time - timedelta(days=3)
                        end_time = last_data_time
                    elif time_interval == "7 nap":
                        start_time = last_data_time - timedelta(days=7)
                        end_time = last_data_time
                    else:
                        start_time = last_data_time - timedelta(hours=1)
                        end_time = last_data_time
                    
                    # Ha nem egyéni intervallum, akkor a korábbi logikát használjuk
                    if time_interval != "Egyéni intervallum":
                        if start_time < first_data_time:
                            start_time = first_data_time
                        end_time = last_data_time
                    
                    # Csak akkor hajtsuk végre a lekérdezést, ha chart_data még None (nem volt hiba)
                    if chart_data is None:
                        # Oszlopok meghatározása a táblánév alapján (feszültség oszlop kizárása)
                        if selected_table == "dfv_smart_db":
                            chart_columns = "id, date, time, trend_smart_t, trend_smart_i1, trend_smart_p, trend_smart_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
                        elif selected_table == "dfv_termosztat_db":
                            chart_columns = "id, date, time, trend_termosztat_t, trend_termosztat_i1, trend_termosztat_p, trend_termosztat_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
                        else:
                            chart_columns = "*"  # Ha más tábla, akkor minden oszlop
                        
                        # Adatok lekérdezése az időintervallum alapján
                        # PostgreSQL: dátum-idő kombinációt használunk
                        query = f"""
                        SELECT {chart_columns} FROM {selected_table} 
                        WHERE (date::text || ' ' || time::text)::timestamp <= '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'::timestamp
                        AND (date::text || ' ' || time::text)::timestamp >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'::timestamp
                        ORDER BY date, time
                        """
                        
                        chart_data = execute_query(query)
                    
                    # Cache-eljük az adatokat, de csak ha van benne adat
                    if chart_data and len(chart_data) > 0:
                        st.session_state.chart_data_cache[cache_key] = chart_data
                    
                except Exception as e:
                    st.error(f"Hiba a diagram generálásakor: {e}")
                    import traceback
                    st.error(f"Részletek: {traceback.format_exc()}")
                    chart_data = None
            
            # Diagram megjelenítése (cache-ből vagy új adatokból)
            # Ellenőrizzük, hogy van-e adat (nem None és nem üres lista)
            if chart_data and len(chart_data) > 0:
                # DataFrame létrehozása a diagramhoz
                chart_df = pd.DataFrame(chart_data)
                
                # Oszlopnevek beállítása - dinamikusan az oszlopok száma szerint
                column_names_chart = ["ID", "Dátum", "Idő", "Harmatpont (°C)", "Hőmérséklet (°C)", 
                                  "Áramerősség (A)", "Teljesítmény (W)", 
                                  "Relatív páratartalom (%)", "Külső páratartalom (%)", "Külső hőmérséklet (°C)"]
                # Csak annyi oszlopnevet használunk, amennyi oszlop van
                available_columns_chart = min(len(column_names_chart), len(chart_df.columns))
                chart_df.columns = column_names_chart[:available_columns_chart]
                
                # Dátum-idő oszlop kombinálása - dinamikusan az oszlopok indexe alapján
                # Ha van legalább 3 oszlop (ID, Dátum, Idő), akkor a 2. és 3. oszlopokat használjuk
                date_time_created = False
                if len(chart_df.columns) >= 3:
                    # Ha van 'Dátum' és 'Idő' oszlop, akkor azokat használjuk
                    if 'Dátum' in chart_df.columns and 'Idő' in chart_df.columns:
                        chart_df['Dátum_Idő'] = pd.to_datetime(chart_df['Dátum'].astype(str) + ' ' + chart_df['Idő'].astype(str))
                        date_time_created = True
                    else:
                        # Egyébként az 1. és 2. oszlopot (0. index után) használjuk dátum és időként
                        chart_df['Dátum_Idő'] = pd.to_datetime(chart_df.iloc[:, 1].astype(str) + ' ' + chart_df.iloc[:, 2].astype(str))
                        date_time_created = True
                elif len(chart_df.columns) >= 2:
                    # Ha csak 2 oszlop van, akkor az elsőt dátumként használjuk
                    chart_df['Dátum_Idő'] = pd.to_datetime(chart_df.iloc[:, 0].astype(str))
                    date_time_created = True
                
                # Ha nem sikerült a dátum-idő kombinálás, akkor nem folytatjuk
                if not date_time_created:
                    st.error("Nincs elegendő oszlop a dátum-idő kombinálásához!")
                else:
                    # Kiválasztott oszlop adatainak előkészítése
                    if selected_column in chart_df.columns:
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
                        st.error(f"A kiválasztott oszlop ({selected_column}) nem létezik az adatokban!")
                    
            else:
                st.warning("Nincs adat a kiválasztott időintervallumban.")
        else:
            st.info("Nincs numerikus oszlop a diagramokhoz.")
    else:
        st.info("Először válassz ki egy táblát a diagramok megjelenítéséhez.")
    
    # CO2 kibocsátási adatok lekérdezése
    st.write("---")
    st.write("## Korábbi 10 nap CO2 kibocsátás adatai")
    
    days_to_show = 10
    
    # API kulcs betöltése a Streamlit secrets-ből
    try:
        api_key = st.secrets["api"]["electricity_maps_token"]
    except (KeyError, FileNotFoundError) as e:
        st.error(f"Hiányzik a .streamlit/secrets.toml fájl vagy az API kulcs. Hiba: {e}")
        api_key = None
    
    # Session state inicializálása
    if 'co2_cached_days' not in st.session_state:
        st.session_state.co2_cached_days = 10
    if 'co2_cached_table' not in st.session_state:
        st.session_state.co2_cached_table = None
    if 'co2_cached_heater_power' not in st.session_state:
        st.session_state.co2_cached_heater_power = None
    
    # Ha változott a fűtőteljesítmény vagy a tábla, töröljük a cache-t
    current_heater_power = st.session_state.get('heater_power', None)
    if (st.session_state.co2_cached_heater_power != current_heater_power):
        # Töröljük a CO2 cache-t, ha változott a fűtőteljesítmény
        if 'co2_hourly_dataframe' in st.session_state:
            del st.session_state['co2_hourly_dataframe']
        if 'co2_hourly_with_power' in st.session_state:
            del st.session_state['co2_hourly_with_power']
        if 'co2_daily_dataframe' in st.session_state:
            del st.session_state['co2_daily_dataframe']
        if 'power_co2_pairs' in st.session_state:
            del st.session_state['power_co2_pairs']
        st.session_state.co2_cached_heater_power = current_heater_power
    
    auto_refresh = ('co2_hourly_dataframe' not in st.session_state) or (st.session_state.co2_cached_table != selected_table)
    
    if auto_refresh and api_key:
        with st.spinner("Adatok lekérése folyamatban..."):
            # Fűtőteljesítmény lekérése session state-ből
            heater_power = st.session_state.get('heater_power', None)
            result = fetch_co2_emission_data(days_to_show, api_key, selected_table, heater_power)
            
            if result and len(result) >= 3:
                co2_hourly_df = result[0]
                co2_hourly_with_power = result[1]
                daily_co2_df = result[2]
                power_co2_pairs = result[3] if len(result) > 3 else None
                
                if co2_hourly_df is not None:
                    # Adatok cache-elése
                    st.session_state['co2_hourly_dataframe'] = co2_hourly_df
                    st.session_state['co2_cached_days'] = days_to_show
                    st.session_state['co2_cached_table'] = selected_table
                    
                    if co2_hourly_with_power is not None and daily_co2_df is not None:
                        st.session_state['co2_hourly_with_power'] = co2_hourly_with_power
                        st.session_state['co2_daily_dataframe'] = daily_co2_df
                        if power_co2_pairs is not None:
                            st.session_state['power_co2_pairs'] = power_co2_pairs
                    else:
                        st.warning("Nincs energiafogyasztási adat az adatbázisban az időszakra.")
    
    
    if 'co2_hourly_dataframe' in st.session_state and st.session_state['co2_hourly_dataframe'] is not None:
        co2_hourly_df = st.session_state['co2_hourly_dataframe']
        
        # Órás CO2 kibocsátás megjelenítése
        if 'co2_hourly_with_power' in st.session_state and st.session_state['co2_hourly_with_power'] is not None:
            co2_hourly_with_power = st.session_state['co2_hourly_with_power']
            
            
            # Diagram - Teljesítmény vs CO2 kibocsátás (W-ban és grammban)
            # Minden egyedi teljesítményértékhez tartozó CO2 kibocsátást mutatjuk
            fig2 = go.Figure()
            
            # Ha van power_co2_pairs (minden egyedi mérési pont), azt használjuk
            if 'power_co2_pairs' in st.session_state and st.session_state['power_co2_pairs'] is not None:
                power_co2_data = st.session_state['power_co2_pairs']
                valid_data = power_co2_data.dropna(subset=['Teljesítmény (W)', 'CO2 (g)'])
                valid_data = valid_data[(valid_data['Teljesítmény (W)'] > 0) & (valid_data['CO2 (g)'] > 0)]
            else:
                # Ha nincs, akkor az órás átlagokat használjuk
                valid_data = co2_hourly_with_power.dropna(subset=['Óras átlagos teljesítmény (W)', 'Óras CO2 (g)'])
                valid_data = valid_data[(valid_data['Óras átlagos teljesítmény (W)'] > 0) & (valid_data['Óras CO2 (g)'] > 0)]
                if len(valid_data) > 0:
                    valid_data = valid_data.rename(columns={'Óras átlagos teljesítmény (W)': 'Teljesítmény (W)', 'Óras CO2 (g)': 'CO2 (g)'})
            
            if len(valid_data) > 0:
                # Értékek W-ban és grammban (alapértelmezett mértékegységek)
                valid_data_display = valid_data.copy()
                
                fig2.add_trace(go.Scatter(
                    x=valid_data_display['Teljesítmény (W)'],
                    y=valid_data_display['CO2 (g)'],
                    mode='markers',
                    name='CO2 kibocsátás vs Teljesítmény',
                    marker=dict(
                        color='#EA1C0A',
                        size=4,
                        opacity=0.6,
                        line=dict(width=0.5, color='#C41608')
                    ),
                    hovertemplate='<b>Teljesítmény:</b> %{x:.2f} W<br>' +
                                '<b>CO2 Kibocsátás:</b> %{y:.2f} g<br>' +
                                '<extra></extra>'
                ))
                
                fig2.update_layout(
                    title="CO2 Kibocsátás vs Teljesítmény",
                    xaxis_title="Teljesítmény (W)",
                    yaxis_title="CO2 Kibocsátás (g)",
                    hovermode='closest',
                    template="plotly_white",
                    height=500
                )
                fig2.update_xaxes(tickformat='.2f', showspikes=True)
                fig2.update_yaxes(tickformat='.2f', showspikes=True)
                
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.warning("Nincs elegendő adat a diagram megjelenítéséhez.")
            
            # Napi adatok - táblázatba szedve (grammban)
            if 'co2_daily_dataframe' in st.session_state and st.session_state['co2_daily_dataframe'] is not None:
                daily_co2_df = st.session_state['co2_daily_dataframe']
                
                st.write("---")
                st.write("### Korábbi 10 nap CO2 kibocsátás összesített adatai")
                display_daily_df = daily_co2_df[['Dátum', 'Napi energia (kWh)', 'Átlag CO2 (g CO2/kWh)', 'Napi CO2 (g)']].copy()
                display_daily_df.columns = ['Dátum', 'Energia (kWh)', 'CO2 intenzitás (g/kWh)', 'Napi CO2 kibocsátás (g)']
                st.dataframe(display_daily_df, use_container_width=True)
            
            # Statisztikák (órás bontásba) - grammban
            # Összes CO2 metrika eltávolítva
        
        
        elif 'co2_daily_dataframe' in st.session_state and st.session_state['co2_daily_dataframe'] is not None:
            daily_co2_df = st.session_state['co2_daily_dataframe']
            
            st.write("### Korábbi 10 nap CO2 kibocsátás")
            
            
            fig2 = go.Figure()
            
            
            if 'Napi átlagos teljesítmény (W)' in daily_co2_df.columns:
                valid_data = daily_co2_df.dropna(subset=['Napi átlagos teljesítmény (W)', 'Napi CO2 (g)'])
                valid_data = valid_data[(valid_data['Napi átlagos teljesítmény (W)'] > 0) & (valid_data['Napi CO2 (g)'] > 0)]
                
                if len(valid_data) > 0:
                    # Értékek W-ban és grammban (alapértelmezett mértékegységek)
                    valid_data_display = valid_data.copy()
                    
                    fig2.add_trace(go.Scatter(
                        x=valid_data_display['Napi átlagos teljesítmény (W)'],
                        y=valid_data_display['Napi CO2 (g)'],
                        mode='markers',
                        name='Napi CO2 kibocsátás vs Teljesítmény',
                        marker=dict(
                            color='#EA1C0A',
                            size=8,
                            opacity=0.7,
                            line=dict(width=2, color='#C41608')
                        ),
                        hovertemplate='<b>Teljesítmény:</b> %{x:.2f} W<br>' +
                                    '<b>CO2 Kibocsátás:</b> %{y:.2f} g<br>' +
                                    '<extra></extra>'
                    ))
                    
                    fig2.update_layout(
                        title="Napi CO2 Kibocsátás vs Teljesítmény",
                        xaxis_title="Teljesítmény (W)",
                        yaxis_title="CO2 Kibocsátás (g)",
                        hovermode='closest',
                        template="plotly_white",
                        height=500
                    )
                    fig2.update_xaxes(tickformat='.2f', showspikes=True)
                    fig2.update_yaxes(tickformat='.2f', showspikes=True)
                    
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.warning("Nincs elegendő adat a diagram megjelenítéséhez.")
            
            # Statisztikák - grammban
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_daily_co2_g = daily_co2_df['Napi CO2 (g)'].mean()
                st.metric("Átlagos napi CO2", f"{avg_daily_co2_g:.2f} g")
            with col2:
                max_daily_co2_g = daily_co2_df['Napi CO2 (g)'].max()
                st.metric("Maximum napi CO2", f"{max_daily_co2_g:.2f} g")
            with col3:
                st.metric("Napok száma", len(daily_co2_df))
            
            # Táblázatos megjelenítés - grammban
            st.write("### Részletes napi adatok")
            display_df = daily_co2_df[['Dátum', 'Napi energia (kWh)', 'Átlag CO2 (g CO2/kWh)', 'Napi CO2 (g)']].copy()
            display_df.columns = ['Dátum', 'Energia (kWh)', 'CO2 intenzitás (g/kWh)', 'Napi CO2 (g)']
            st.dataframe(display_df, use_container_width=True)
    