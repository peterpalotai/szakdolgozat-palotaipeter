import streamlit as st
import pandas as pd
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