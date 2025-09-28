import streamlit as st
import pandas as pd
from database import get_db_connection, test_db_connection, execute_query



def show_home_page():
    
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
    

    
    # Elemek száma beállítása
    col1, col2 = st.columns([1, 2])
    
    with col1:
        page_size = st.selectbox(
            "Elemek száma:",
            [5, 10, 15, 20, 25, 50],
            index=0,
            key="page_size_selector"
        )
    
    with col2:
        st.write("")  # Üres sor a szép elrendezéshez
    
    # Session state inicializálása a lapozáshoz
    if f"offset_{selected_table}" not in st.session_state:
        st.session_state[f"offset_{selected_table}"] = 0
    
    # Ha megváltozott a page_size, reseteljük az offset-et
    if f"last_page_size_{selected_table}" not in st.session_state:
        st.session_state[f"last_page_size_{selected_table}"] = page_size
    elif st.session_state[f"last_page_size_{selected_table}"] != page_size:
        st.session_state[f"offset_{selected_table}"] = 0
        st.session_state[f"last_page_size_{selected_table}"] = page_size
    
    # Adatok lekérdezése - automatikusan fut
    try:
        query = f"SELECT * FROM {selected_table} LIMIT {page_size} OFFSET {st.session_state[f'offset_{selected_table}']}"
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
            

            
            # Lapozó gombok
            col1, col2, col3, col4, col5 = st.columns([0.1, 0.1, 0.1, 0.1,0.1])
            
            with col1:
                if st.button("⏮️"):
                    st.session_state[f"offset_{selected_table}"] = 0
                    st.rerun()
            
            with col2:
                if st.button("⬅️"):
                    if st.session_state[f"offset_{selected_table}"] >= page_size:
                        st.session_state[f"offset_{selected_table}"] -= page_size
                        st.rerun()
            
            with col3:
                if st.button("➡️"):
                    st.session_state[f"offset_{selected_table}"] += page_size
                    st.rerun()
            
            with col4:
                if st.button("⏭️"):
                    # Az utolsó oldal kiszámítása
                    try:
                        # Összes rekord számának lekérdezése
                        count_query = f"SELECT COUNT(*) FROM {selected_table}"
                        total_count = execute_query(count_query)[0][0]
                        
                        # Utolsó oldal offset számítása
                        last_page_offset = (total_count // page_size) * page_size
                        st.session_state[f"offset_{selected_table}"] = last_page_offset
                        st.rerun()
                    except Exception as e:
                        st.error(f"Hiba az utolsó oldal kiszámításakor: {e}")
                        # Fallback: nagy szám használata
                        st.session_state[f"offset_{selected_table}"] = 1000
                        st.rerun()
            
            with col5:
                # Jelenlegi oldal és összes oldal információ
                current_page = (st.session_state[f"offset_{selected_table}"] // page_size) + 1
            
            # Összes oldal számának kiszámítása
                try:
                    count_query = f"SELECT COUNT(*) FROM {selected_table}"
                    total_count = execute_query(count_query)[0][0]
                    total_pages = (total_count + page_size - 1) // page_size  # Felfelé kerekítés
                    st.write(f" **Oldal:** {current_page} / {total_pages}")
                except Exception as e:
                    st.write(f"**Oldal:** {current_page}")
            
        else:
            st.warning("Nincs adat a kiválasztott táblában.")
            
    except Exception as e:
        st.error(f"Adatbázishiba: {e}")
        st.write("Ellenőrizd, hogy a kiválasztott tábla létezik-e az adatbázisban.")