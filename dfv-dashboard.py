import streamlit as st
from page_modules.home_page import show_home_page
from page_modules.energy_prediction_page import show_energy_prediction_page
from page_modules.dfv_prediction_page import show_dfv_prediction_page
# CSS a Streamlit alapértelmezett oldal navigáció elrejtéséhez


# Oldalsáv navigáció
st.sidebar.title("DFV Dashboard")
st.sidebar.markdown("---")

# Navigációs gombok
if st.sidebar.button("🏠 Főoldal", use_container_width=True):
    st.session_state.page = "🏠 Főoldal"

if st.sidebar.button("⚡ Energia és ár előrejelzés", use_container_width=True):
    st.session_state.page = "⚡ Energia és ár előrejelzés"

if st.sidebar.button("🌡️ DFV be/kikapcsolás előrejelzés", use_container_width=True):
    st.session_state.page = "🌡️ DFV be/kikapcsolás előrejelzés"

# Session state inicializálása
if "page" not in st.session_state:
    st.session_state.page = "🏠 Főoldal"

# Oldal változó
page = st.session_state.page

# Oldal megjelenítése
if page == "🏠 Főoldal":
    show_home_page()
elif page == "⚡ Energia és ár előrejelzés":
    show_energy_prediction_page()
elif page == "🌡️ DFV be/kikapcsolás előrejelzés":
    show_dfv_prediction_page()
