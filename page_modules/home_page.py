import streamlit as st
from database import get_db_connection, test_db_connection, execute_query

def show_home_page():
    """Főoldal megjelenítése"""
    st.write("# DFV Dashboard")
    st.write("Üdvözöljük a DFV Dashboard-on!")
    
    # Database connection test
    if st.button("Adatbázis teszt"):
        if test_db_connection():
            st.success("Sikeres csatlakozás")
        else:
            st.error("Sikertelen csatlakozás")

    # Példa adatbázis műveletek
    st.write("## Adatbázis műveletek")

    try:
        db = get_db_connection()
        
        if st.button("Példa lekérdezés"):
            result = execute_query("SELECT time FROM dfv_smart_db")
            if result:
                st.write("Az adott időpont:", result[2][0])
            else:
                st.write("Nem tért vissza érték")
                
    except Exception as e:
        st.error(f"Adatbázishiba: {e}")