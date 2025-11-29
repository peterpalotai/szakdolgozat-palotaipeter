import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, time
from app_services.database import test_db_connection, execute_query
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_services.co2_calculation import fetch_co2_emission_data

LAST_DATA_TIME = datetime(2025, 8, 21, 23, 45, 0)
FIRST_DATA_TIME = datetime(2024, 8, 19, 8, 0, 0)
DAYS_TO_SHOW = 10


"CSS fájl betöltése."
def _load_css():
    try:
        with open('styles.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


"Táblázat session state inicializálása."
def _initialize_table_session_state():
    if "selected_table" not in st.session_state:
        st.session_state.selected_table = "dfv_smart_db"
        st.session_state.table_display_name = "Dinamikus fűtésvezérlő"
        st.session_state.prev_selected_table = None
    if "global_page_size" not in st.session_state:
        st.session_state.global_page_size = 5
    if "chart_generated" not in st.session_state:
        st.session_state.chart_generated = False
    if "chart_data_cache" not in st.session_state:
        st.session_state.chart_data_cache = {}


"Cache törlése tábla váltáskor."
def _clear_cache_on_table_change(selected_table):
    if "prev_selected_table" in st.session_state and st.session_state.prev_selected_table != selected_table:
        if "chart_data_cache" in st.session_state:
            keys_to_delete = [key for key in st.session_state.chart_data_cache.keys() 
                             if key.startswith(f"{st.session_state.prev_selected_table}_")]
            for key in keys_to_delete:
                del st.session_state.chart_data_cache[key]
        
        for key in ['co2_hourly_dataframe', 'co2_hourly_with_power', 'co2_daily_dataframe', 'co2_cached_days']:
            if key in st.session_state:
                del st.session_state[key]
        
        if f"offset_{selected_table}" in st.session_state:
            st.session_state[f"offset_{selected_table}"] = 0
        
        st.session_state.prev_selected_table = selected_table


"Tábla kiválasztó gomb létrehozása."
def _select_table_button(table_name, display_name, is_selected):
    button_type = "primary" if is_selected else "secondary"
    if st.button(display_name, use_container_width=True, type=button_type):
        st.session_state.prev_selected_table = st.session_state.selected_table
        st.session_state.selected_table = table_name
        st.session_state.table_display_name = display_name
        st.rerun()


"Táblák kiválasztásának megjelenítése."
def _display_table_selection(selected_table):
    col1, col2 = st.columns(2)
    with col1:
        _select_table_button("dfv_smart_db", "Dinamikus fűtésvezérlő", selected_table == "dfv_smart_db")
    with col2:
        _select_table_button("dfv_termosztat_db", "Termosztátos vezérlő", selected_table == "dfv_termosztat_db")


"Oldal méret beállítása."
def _setup_page_size():
    col1, col2 = st.columns([1, 2])
    with col1:
        page_size_options = [5, 15, 25]
        current_page_size = st.session_state.global_page_size
        try:
            current_index = page_size_options.index(current_page_size)
        except ValueError:
            current_index = 0
        
        page_size = st.selectbox("Elemek száma:", page_size_options, index=current_index, key="global_page_size_selector")
        st.session_state.global_page_size = page_size
    with col2:
        st.write("")


"Táblázat oszlopok lekérdezése."
def _get_table_columns(selected_table):
    if selected_table == "dfv_smart_db":
        return "id, date, time, trend_smart_dp, trend_smart_t, trend_smart_i1, trend_smart_p, trend_smart_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
    elif selected_table == "dfv_termosztat_db":
        return "id, date, time, trend_termosztat_t, trend_termosztat_i1, trend_termosztat_p, trend_termosztat_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
    return "*"


"Oszlopnevek meghatározása tábla típus alapján."
def _get_column_names(selected_table):
    if selected_table == "dfv_termosztat_db":
        return ["Dátum", "Idő", "Belső hőmérséklet (°C)", "Áramerősség (A)", "Teljesítmény (W)", 
                "Relatív páratartalom (%)", "Külső páratartalom (g/m³)", "Külső hőmérséklet (°C)"]
    return ["Dátum", "Idő", "Harmatpont (°C)", "Belső hőmérséklet (°C)", "Áramerősség (A)", "Teljesítmény (W)", 
            "Relatív páratartalom (%)", "Külső páratartalom (g/m³)", "Külső hőmérséklet (°C)"]


"DataFrame előkészítése megjelenítéshez."
def _prepare_dataframe_for_display(df, selected_table):
    column_names = _get_column_names(selected_table)
    
    if len(df.columns) > 1:
        df_display = df.iloc[:, 1:]
        available_columns = min(len(column_names), len(df_display.columns))
        df_display.columns = column_names[:available_columns]
    else:
        df_display = df
        if len(df_display.columns) > 0:
            df_display.columns = column_names[:len(df_display.columns)]
    
    for i, col in enumerate(df_display.columns):
        if i >= 2:
            try:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce')
                if df_display[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                    if col == "Teljesítmény (W)":
                        df_display[col] = df_display[col] * 1000
                    df_display[col] = df_display[col].round(2)
            except:
                pass
    
    return df_display


"Lapozás vezérlőelemek megjelenítése."
def _display_pagination_controls(selected_table, total_count):
    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 0.2, 0.2, 0.2, 0.2, 0.1, 0.3])
    
    with col1:
        st.write("")
    
    with col2:
        if st.button("⏮️"):
            st.session_state[f"offset_{selected_table}"] = 0
            st.rerun()
    
    with col3:
        current_page_size = st.session_state.global_page_size
        if st.button("⬅️"):
            if st.session_state[f"offset_{selected_table}"] >= current_page_size:
                st.session_state[f"offset_{selected_table}"] -= current_page_size
                st.rerun()
    
    with col4:
        current_page_size = st.session_state.global_page_size
        current_offset = st.session_state[f"offset_{selected_table}"]
        next_offset = current_offset + current_page_size
        has_next_page = next_offset < total_count
        
        if st.button("➡️", disabled=not has_next_page):
            st.session_state[f"offset_{selected_table}"] = next_offset
            st.rerun()
    
    with col5:
        current_page_size = st.session_state.global_page_size
        current_offset = st.session_state[f"offset_{selected_table}"]
        
        try:
            from page_modules.database_queries import get_table_count
            count_query = get_table_count(selected_table)
            total_count = execute_query(count_query)[0][0]
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
        current_page_size = st.session_state.global_page_size
        current_page = (st.session_state[f"offset_{selected_table}"] // current_page_size) + 1
        
        try:
            from page_modules.database_queries import get_table_count
            count_query = get_table_count(selected_table)
            total_count = execute_query(count_query)[0][0]
            total_pages = (total_count + current_page_size - 1) // current_page_size
            st.write(f" **Oldal:** {current_page} / {total_pages}")
        except Exception as e:
            st.write(f"**Oldal:** {current_page}")


"Időintervallum meghatározása."
def _get_time_range(time_interval, custom_start_date=None, custom_end_date=None):
    if time_interval == "Egyéni intervallum":
        if custom_start_date and custom_end_date:
            start_time = datetime.combine(custom_start_date, time(0, 0, 0))
            end_time = datetime.combine(custom_end_date, time(23, 59, 59))
            if start_time < FIRST_DATA_TIME:
                start_time = FIRST_DATA_TIME
            if end_time > LAST_DATA_TIME:
                end_time = LAST_DATA_TIME
            if start_time > end_time:
                return None, None
            return start_time, end_time
        return FIRST_DATA_TIME, LAST_DATA_TIME
    
    intervals = {
        "1 óra": timedelta(hours=1),
        "3 óra": timedelta(hours=3),
        "12 óra": timedelta(hours=12),
        "1 nap": timedelta(days=1),
        "3 nap": timedelta(days=3),
        "7 nap": timedelta(days=7)
    }
    
    delta = intervals.get(time_interval, timedelta(hours=1))
    start_time = LAST_DATA_TIME - delta
    if start_time < FIRST_DATA_TIME:
        start_time = FIRST_DATA_TIME
    return start_time, LAST_DATA_TIME


"Diagram oszlopok lekérdezése."
def _get_chart_columns(selected_table):
    if selected_table == "dfv_smart_db":
        return "id, date, time, trend_smart_dp, trend_smart_t, trend_smart_i1, trend_smart_p, trend_smart_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
    elif selected_table == "dfv_termosztat_db":
        return "id, date, time, trend_termosztat_t, trend_termosztat_i1, trend_termosztat_p, trend_termosztat_rh, trend_kulso_paratartalom, trend_kulso_homerseklet_pillanatnyi"
    return "*"


"Diagram adatok lekérdezése cache-ből vagy adatbázisból."
def _fetch_chart_data(selected_table, time_interval, custom_start_date=None, custom_end_date=None):
    cache_key = f"{selected_table}_{time_interval}"
    if time_interval == "Egyéni intervallum" and custom_start_date and custom_end_date:
        cache_key = f"{selected_table}_{time_interval}_{custom_start_date}_{custom_end_date}"
    
    if cache_key in st.session_state.chart_data_cache:
        cached_data = st.session_state.chart_data_cache[cache_key]
        if cached_data and len(cached_data) > 0:
            return cached_data
    
    start_time, end_time = _get_time_range(time_interval, custom_start_date, custom_end_date)
    if start_time is None or end_time is None:
        return []
    
    try:
        from page_modules.database_queries import get_chart_data_by_time_range
        chart_columns = _get_chart_columns(selected_table)
        query = get_chart_data_by_time_range(
            selected_table, chart_columns,
            start_time.strftime('%Y-%m-%d %H:%M:%S'),
            end_time.strftime('%Y-%m-%d %H:%M:%S')
        )
        chart_data = execute_query(query)
        
        if chart_data and len(chart_data) > 0:
            st.session_state.chart_data_cache[cache_key] = chart_data
        
        return chart_data or []
    except Exception as e:
        st.error(f"Hiba a diagram generálásakor: {e}")
        import traceback
        st.error(f"Részletek: {traceback.format_exc()}")
        return []


"Diagram DataFrame előkészítése."
def _prepare_chart_dataframe(chart_data, selected_table):
    chart_df = pd.DataFrame(chart_data)
    
    if selected_table == "dfv_termosztat_db":
        column_names = ["ID", "Dátum", "Idő", "Belső hőmérséklet (°C)", "Áramerősség (A)", "Teljesítmény (W)", 
                       "Relatív páratartalom (%)", "Külső páratartalom (g/m³)", "Külső hőmérséklet (°C)"]
    else:
        column_names = ["ID", "Dátum", "Idő", "Harmatpont (°C)", "Belső hőmérséklet (°C)", "Áramerősség (A)", 
                       "Teljesítmény (W)", "Relatív páratartalom (%)", "Külső páratartalom (g/m³)", "Külső hőmérséklet (°C)"]
    
    available_columns = min(len(column_names), len(chart_df.columns))
    chart_df.columns = column_names[:available_columns]
    
    if "Teljesítmény (W)" in chart_df.columns:
        chart_df["Teljesítmény (W)"] = pd.to_numeric(chart_df["Teljesítmény (W)"], errors='coerce') * 1000
    
    if len(chart_df.columns) >= 3:
        if 'Dátum' in chart_df.columns and 'Idő' in chart_df.columns:
            chart_df['Dátum_Idő'] = pd.to_datetime(chart_df['Dátum'].astype(str) + ' ' + chart_df['Idő'].astype(str))
        else:
            chart_df['Dátum_Idő'] = pd.to_datetime(chart_df.iloc[:, 1].astype(str) + ' ' + chart_df.iloc[:, 2].astype(str))
    elif len(chart_df.columns) >= 2:
        chart_df['Dátum_Idő'] = pd.to_datetime(chart_df.iloc[:, 0].astype(str))
    else:
        return None
    
    return chart_df


"Diagram létrehozása Plotly-val."
def _create_chart(chart_df, selected_column):
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
    fig.update_xaxes(tickformat="%m-%d %H:%M", tickangle=45)
    return fig


"Diagram statisztikák megjelenítése."
def _display_chart_statistics(chart_df, selected_column):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Minimális érték", f"{chart_df[selected_column].min():.2f}")
    with col2:
        st.metric("Maximális érték", f"{chart_df[selected_column].max():.2f}")
    with col3:
        st.metric("Átlag", f"{chart_df[selected_column].mean():.2f}")
    with col4:
        st.metric("Mérések száma", len(chart_df))


"Diagram szekció megjelenítése."
def _display_chart_section(df_display, selected_table):
    numeric_columns = []
    for i, col in enumerate(df_display.columns):
        if i >= 2:
            try:
                pd.to_numeric(df_display[col], errors='coerce')
                numeric_columns.append(col)
            except:
                pass
    
    if not numeric_columns:
        st.info("Nincs numerikus oszlop a diagramokhoz.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        selected_column = st.selectbox("Válassz oszlopot a diagramhoz:", numeric_columns, key="chart_column_selector")
    with col2:
        time_interval = st.selectbox("Időintervallum:", 
                                    ["1 óra", "3 óra", "12 óra", "1 nap", "3 nap", "7 nap", "Egyéni intervallum"],
                                    key="time_interval_selector")
    
    custom_start_date = None
    custom_end_date = None
    generate_chart = False
    
    if time_interval == "Egyéni intervallum":
        col3, col4 = st.columns(2)
        with col3:
            custom_start_date = st.date_input("Kezdő dátum:", value=datetime(2025, 8, 11).date(),
                                             min_value=datetime(2024, 8, 19).date(),
                                             max_value=datetime(2025, 8, 21).date(), key="custom_start_date")
        with col4:
            custom_end_date = st.date_input("Végdátum:", value=datetime(2025, 8, 21).date(),
                                           min_value=datetime(2024, 8, 19).date(),
                                           max_value=datetime(2025, 8, 21).date(), key="custom_end_date")
        if st.button("Diagram generálása", type="primary"):
            generate_chart = True
            if f"{selected_table}_{selected_column}_{time_interval}_{custom_start_date}_{custom_end_date}" in st.session_state.chart_data_cache:
                del st.session_state.chart_data_cache[f"{selected_table}_{selected_column}_{time_interval}_{custom_start_date}_{custom_end_date}"]
    
    if time_interval == "Egyéni intervallum" and not generate_chart:
        return
    
    chart_data = _fetch_chart_data(selected_table, time_interval, custom_start_date, custom_end_date)
    
    if chart_data and len(chart_data) > 0:
        chart_df = _prepare_chart_dataframe(chart_data, selected_table)
        if chart_df is None:
            st.error("Nincs elegendő oszlop a dátum-idő kombinálásához!")
            return
        
        if selected_column in chart_df.columns:
            chart_df[selected_column] = pd.to_numeric(chart_df[selected_column], errors='coerce')
            fig = _create_chart(chart_df, selected_column)
            st.plotly_chart(fig, use_container_width=True)
            st.session_state.chart_generated = True
            _display_chart_statistics(chart_df, selected_column)
        else:
            st.error(f"A kiválasztott oszlop ({selected_column}) nem létezik az adatokban!")
    else:
        st.warning("Nincs adat a kiválasztott időintervallumban.")


"CO2 session state inicializálása."
def _initialize_co2_session_state():
    if 'co2_cached_days' not in st.session_state:
        st.session_state.co2_cached_days = 10
    if 'co2_cached_table' not in st.session_state:
        st.session_state.co2_cached_table = None
    if 'co2_cached_heater_power' not in st.session_state:
        st.session_state.co2_cached_heater_power = None


"CO2 cache törlése változás esetén."
def _clear_co2_cache_on_change(selected_table):
    current_heater_power = st.session_state.get('heater_power', None)
    if st.session_state.co2_cached_heater_power != current_heater_power:
        for key in ['co2_hourly_dataframe', 'co2_hourly_with_power', 'co2_daily_dataframe', 'power_co2_pairs']:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.co2_cached_heater_power = current_heater_power


"CO2 adatok betöltése."
def _load_co2_data(selected_table):
    auto_refresh = ('co2_hourly_dataframe' not in st.session_state) or (st.session_state.co2_cached_table != selected_table)
    
    if auto_refresh:
        with st.spinner("Adatok lekérése folyamatban..."):
            heater_power = st.session_state.get('heater_power', None)
            result = fetch_co2_emission_data(DAYS_TO_SHOW, None, selected_table, heater_power)
            
            if result and len(result) >= 3:
                co2_hourly_df = result[0]
                co2_hourly_with_power = result[1]
                daily_co2_df = result[2]
                power_co2_pairs = result[3] if len(result) > 3 else None
                
                if co2_hourly_df is not None:
                    st.session_state['co2_hourly_dataframe'] = co2_hourly_df
                    st.session_state['co2_cached_days'] = DAYS_TO_SHOW
                    st.session_state['co2_cached_table'] = selected_table
                    
                    if co2_hourly_with_power is not None and daily_co2_df is not None:
                        st.session_state['co2_hourly_with_power'] = co2_hourly_with_power
                        st.session_state['co2_daily_dataframe'] = daily_co2_df
                        if power_co2_pairs is not None:
                            st.session_state['power_co2_pairs'] = power_co2_pairs
                    else:
                        st.warning("Nincs energiafogyasztási adat az adatbázisban az időszakra.")


"CO2 táblázat oldal méret beállítása."
def _setup_co2_page_size():
    if "co2_page_size" not in st.session_state:
        st.session_state.co2_page_size = 5
    if "prev_co2_page_size" not in st.session_state:
        st.session_state.prev_co2_page_size = st.session_state.co2_page_size
    
    col1, col2 = st.columns([1, 2])
    with col1:
        page_size_options = [5, 15, 25]
        current_co2_page_size = st.session_state.co2_page_size
        try:
            current_index = page_size_options.index(current_co2_page_size)
        except ValueError:
            current_index = 0
        
        co2_page_size = st.selectbox("Elemek száma:", page_size_options, index=current_index, key="co2_page_size_selector")
        
        if co2_page_size != st.session_state.prev_co2_page_size:
            st.session_state.co2_table_offset = 0
            st.session_state.prev_co2_page_size = co2_page_size
        
        st.session_state.co2_page_size = co2_page_size
    with col2:
        st.write("")


"CO2 DataFrame előkészítése megjelenítéshez."
def _prepare_co2_display_df(daily_co2_df):
    available_columns = []
    for col in ['Dátum', 'Napi energia (kWh)', 'Napi CO2 (g)']:
        if col in daily_co2_df.columns:
            available_columns.append(col)
    
    if available_columns:
        display_df = daily_co2_df[available_columns].copy()
        column_mapping = {
            'Dátum': 'Dátum',
            'Napi energia (kWh)': 'Adott nap teljes fogyasztása (kWh)',
            'Napi CO2 (g)': 'CO2 kibocsátás (g)'
        }
        display_df.columns = [column_mapping.get(col, col) for col in display_df.columns]
        display_df['Dátum'] = pd.to_datetime(display_df['Dátum']).dt.strftime('%Y-%m-%d')
        
        for col in ['Fogyasztás (kWh)', 'CO2 kibocsátás (g)']:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(2)
        
        return display_df
    return pd.DataFrame()


"CO2 táblázat lapozás vezérlőelemek megjelenítése."
def _display_co2_pagination_controls(total_rows):
    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 0.2, 0.2, 0.2, 0.2, 0.1, 0.3])
    
    with col1:
        st.write("")
    with col2:
        if st.button("⏮️", key="co2_first_page"):
            st.session_state.co2_table_offset = 0
            st.rerun()
    with col3:
        current_page_size = st.session_state.co2_page_size
        if st.button("⬅️", key="co2_prev_page"):
            if st.session_state.co2_table_offset >= current_page_size:
                st.session_state.co2_table_offset -= current_page_size
                st.rerun()
    with col4:
        current_page_size = st.session_state.co2_page_size
        next_offset = st.session_state.co2_table_offset + current_page_size
        has_next_page = next_offset < total_rows
        
        if st.button("➡️", disabled=not has_next_page, key="co2_next_page"):
            st.session_state.co2_table_offset = next_offset
            st.rerun()
    with col5:
        current_page_size = st.session_state.co2_page_size
        last_page_offset = ((total_rows - 1) // current_page_size) * current_page_size
        is_on_last_page = st.session_state.co2_table_offset >= last_page_offset
        
        if st.button("⏭️", disabled=is_on_last_page, key="co2_last_page"):
            st.session_state.co2_table_offset = last_page_offset
            st.rerun()
    with col6:
        st.write("")
    with col7:
        current_page_size = st.session_state.co2_page_size
        current_page = (st.session_state.co2_table_offset // current_page_size) + 1
        total_pages = (total_rows + current_page_size - 1) // current_page_size
        st.write(f" **Oldal:** {current_page} / {total_pages}")


"CO2 táblázat megjelenítése."
def _display_co2_table():
    if 'co2_hourly_dataframe' not in st.session_state or st.session_state['co2_hourly_dataframe'] is None:
        return
    
    if 'co2_daily_dataframe' not in st.session_state or st.session_state['co2_daily_dataframe'] is None:
        return
    
    daily_co2_df = st.session_state['co2_daily_dataframe']
    
    st.write("---")
    st.write("## CO2 kibocsátás")
    
    _setup_co2_page_size()
    
    if "co2_table_offset" not in st.session_state:
        st.session_state.co2_table_offset = 0
    
    display_df = _prepare_co2_display_df(daily_co2_df)
    
    if display_df.empty:
        return
    
    current_page_size = st.session_state.co2_page_size
    total_rows = len(display_df)
    start_idx = st.session_state.co2_table_offset
    end_idx = min(start_idx + current_page_size, total_rows)
    display_df_paginated = display_df.iloc[start_idx:end_idx]
    
    st.dataframe(display_df_paginated, use_container_width=True, hide_index=True)
    _display_co2_pagination_controls(total_rows)


"Táblázat adatok lekérdezése adatbázisból."
def _fetch_table_data(selected_table):
    try:
        current_page_size = st.session_state.global_page_size
        columns = _get_table_columns(selected_table)
        
        from page_modules.database_queries import get_table_data_paginated
        query = get_table_data_paginated(selected_table, columns, current_page_size, 
                                        st.session_state[f'offset_{selected_table}'])
        result = execute_query(query)
        
        if result:
            df = pd.DataFrame(result)
            df_display = _prepare_dataframe_for_display(df, selected_table)
            
            from page_modules.database_queries import get_table_count
            count_query = get_table_count(selected_table)
            total_count = execute_query(count_query)[0][0]
            
            return df_display, total_count
        return None, 0
    except Exception as e:
        st.error(f"Adatbázishiba: {e}")
        st.write("Ellenőrizd, hogy a kiválasztott tábla létezik-e az adatbázisban.")
        return None, 0


"Főoldal megjelenítése."
def show_home_page():
    _load_css()
    st.write("# Főoldal")
    
    if st.button("Adatbázis teszt"):
        if test_db_connection():
            st.success("Sikeres csatlakozás")
        else:
            st.error("Sikertelen csatlakozás")
    
    st.write("---")
    st.write("## Adatbázis lekérdezés")
    
    _initialize_table_session_state()
    
    selected_table = st.session_state.selected_table
    table_display_name = st.session_state.table_display_name
    
    _clear_cache_on_table_change(selected_table)
    _display_table_selection(selected_table)
    _setup_page_size()
    
    if f"offset_{selected_table}" not in st.session_state:
        st.session_state[f"offset_{selected_table}"] = 0
    
    df_display, total_count = _fetch_table_data(selected_table)
    
    if df_display is not None:
        st.write(f"### {table_display_name} adatai")
        st.dataframe(df_display, use_container_width=True, hide_index=False)
        _display_pagination_controls(selected_table, total_count)
    
    st.write("---")
    st.write("##  Historikus adatok vizuális lekérése")
    
    if df_display is not None and not df_display.empty:
        _display_chart_section(df_display, selected_table)
    else:
        st.info("Először válassz ki egy táblát a diagramok megjelenítéséhez.")
    
    _initialize_co2_session_state()
    _clear_co2_cache_on_change(selected_table)
    _load_co2_data(selected_table)
    _display_co2_table()
