import streamlit as st
from database import get_db_connection, test_db_connection, execute_query

# Oldalsáv navigáció
st.sidebar.title("DFV Dashboard")
st.sidebar.markdown("---")

# Navigációs gombok
if st.sidebar.button("🏠 Főoldal", use_container_width=True):
    st.session_state.page = "Főoldal"

if st.sidebar.button("⚡ Energia és ár előrejelzés", use_container_width=True):
    st.session_state.page = "Energia és ár előrejelzés"

if st.sidebar.button("🌡️ DFV be/kikapcsolás előrejelzés", use_container_width=True):
    st.session_state.page = "DFV be/kikapcsolás előrejelzés"

# Session state inicializálása
if "page" not in st.session_state:
    st.session_state.page = "Főoldal"


# Oldal változó
page = st.session_state.page

# Főoldal
if page == "Főoldal":
    st.write("# DFV Dashboard")
    st.write("Üdvözöljük a DFV Dashboard-on!")
    
    # Database connection test
    if st.button("Adatbázis teszt"):
        if test_db_connection():
            st.success("Sikeres csatlakozás")
        else:
            st.error("Sikertelen csatlakozás")

    #Példa adatbázis műveletek
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

# Energia és ár előrejelzés oldal
elif page == "Energia és ár előrejelzés":
    st.write("# Energia és ár előrejelzés")
    st.write("Fejlesztés alatt")


# DFV be/kikapcsolás előrejelzés oldal
elif page == "DFV be/kikapcsolás előrejelzés":
    st.write("# DFV be/kikapcsolás előrejelzés")
    st.write("Fejlesztés alatt")
