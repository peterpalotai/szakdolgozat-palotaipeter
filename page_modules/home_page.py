import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from database import get_db_connection, test_db_connection, execute_query

def show_home_page():
    #CSS style, hogy a az oldalon megjelenő tartalom teljes szélességűek legyenek
    st.markdown("""
    <style>
    .main .block-container {
        max-width: 80rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    .stMainBlockContainer {
        max-width: 80rem !important;
    }
    
    /* Ensure the styling persists on interactions */
    .main .block-container > div {
        max-width: 80rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.write("# DFV Dashboard")
    
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
    
    # Plot canvas mindig megjelenik, az adatok lekérdezése nélkül is
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
                    ["Utolsó 1 óra", "Utolsó 3 óra", "Utolsó 12 óra", "Utolsó 1 nap", "Utolsó 3 nap", "Egyedi időtartam"],
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
            
            
            if st.button("Lekérdezés", use_container_width=True):
                try:
                    # Időintervallumok megadása
                    last_data_time = datetime(2025, 8, 21, 23, 45, 0) 
                    first_data_time = datetime(2024, 8, 19, 8, 0, 0)
                    
                    if time_interval == "Utolsó 1 óra":
                        start_time = last_data_time - timedelta(hours=1)
                    elif time_interval == "Utolsó 3 óra":
                        start_time = last_data_time - timedelta(hours=3)
                    elif time_interval == "Utolsó 12 óra":
                        start_time = last_data_time - timedelta(hours=12)
                    elif time_interval == "Utolsó 1 nap":
                        start_time = last_data_time - timedelta(days=1)
                    elif time_interval == "Utolsó 3 nap":
                        start_time = last_data_time - timedelta(days=3)
                    elif time_interval == "Egyedi időtartam":
                        if custom_start_time and custom_end_time:
                            start_time = datetime.combine(custom_start_time, datetime.min.time())
                            end_time = datetime.combine(custom_end_time, datetime.max.time())
                        else:
                            st.error("Válassz ki kezdő és befejező dátumot!")
                            st.stop()
                    else:
                        start_time = last_data_time - timedelta(hours=1)
                    
                    # Biztosítjuk, hogy ne menjünk az adathalmaz kezdete előtt
                    if start_time < first_data_time:
                        start_time = first_data_time
                    
                    # Adatok lekérdezése az időintervallum alapján
                    if time_interval == "Egyedi időtartam":
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
                        
                        # Session state frissítése - diagram generálva
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
                        
                except Exception as e:
                    st.error(f"Hiba a diagram generálásakor: {e}")
        else:
            st.info("Nincs numerikus oszlop a diagramokhoz.")
    else:
        st.info("Először válassz ki egy táblát a diagramok megjelenítéséhez.")
    
    
    # Üres plotly csak akkor jelenik meg, ha még nem generáltunk diagramot
    if not st.session_state.get("chart_generated", False):
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text="Válassz ki egy táblát és oszlopot a diagram megjelenítéséhez",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        empty_fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=400
        )
        
        st.plotly_chart(empty_fig, use_container_width=True)