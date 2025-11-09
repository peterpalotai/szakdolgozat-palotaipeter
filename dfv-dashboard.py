import streamlit as st
from app_pages.home_page import show_home_page
from app_pages.energy_prediction_page import show_energy_prediction_page
from app_pages.savings_page import show_savings_page
from app_services.eon_scraper import scrape_eon_prices



# Session state inicializálása
if "page" not in st.session_state:
    st.session_state.page = "Főoldal"

# Oldalsáv navigáció
st.sidebar.title("DFV Monitoring")
st.sidebar.markdown("---")

# Navigációs gombok
if st.sidebar.button("Főoldal", use_container_width=True):
    st.session_state.page = "Főoldal"

if st.sidebar.button("Megtakarítások", use_container_width=True):
    st.session_state.page = "Megtakarítások"

if st.sidebar.button("Energiafogyasztás és megtakarítás előrejelzés", use_container_width=True):
    st.session_state.page = "Energiafogyasztás és megtakarítás előrejelzés"

st.sidebar.markdown("---")

if st.session_state.page != "Főoldal":
    st.sidebar.write("### Fűtőteljesítmény beállítása")
    if 'heater_power' not in st.session_state:
        st.session_state.heater_power = 60.0  

    heater_power = st.sidebar.number_input(
        "Hagyományos fűtőtest teljesítménye (W):",
        min_value=30.0,
        max_value=120.0,
        value=st.session_state.heater_power,
        step=5.0,
        key="heater_power_input",
        help="Az izzó teljesítménye 30 és 120 W között mozoghat."
    )

    st.session_state.heater_power = heater_power

# E.ON árak automatikus lekérése az alkalmazás indításakor
if 'loss_price' not in st.session_state:
    with st.spinner("E.ON árak automatikus lekérése..."):
        loss_price, error = scrape_eon_prices()
    
    if error:
        st.session_state.loss_price = None
        st.session_state.eon_error = error
    else:
        st.session_state.loss_price = loss_price
        st.session_state.eon_error = None

# Oldal változó
page = st.session_state.page

# Oldal megjelenítése
if page == "Főoldal":
    show_home_page()
elif page == "Energiafogyasztás és megtakarítás előrejelzés":
    show_energy_prediction_page()
elif page == "Megtakarítások":
    show_savings_page()
