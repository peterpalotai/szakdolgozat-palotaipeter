import streamlit as st
from page_modules.home_page import show_home_page
from page_modules.energy_prediction_page import show_energy_prediction_page
from page_modules.savings_page import show_savings_page
from app_services.eon_scraper import scrape_eon_prices



# Oldalsáv navigáció
st.sidebar.title("DFV Monitoring")
st.sidebar.markdown("---")

# Navigációs gombok
if st.sidebar.button("🏠 Főoldal", use_container_width=True):
    st.session_state.page = "🏠 Főoldal"

if st.sidebar.button("💰 Megtakarítások", use_container_width=True):
    st.session_state.page = "💰 Megtakarítások"

if st.sidebar.button("⚡ Energiafogyasztás és megtakarítás előrejelzés", use_container_width=True):
    st.session_state.page = "⚡ Energiafogyasztás és megtakarítás előrejelzés"



# Session state inicializálása
if "page" not in st.session_state:
    st.session_state.page = "🏠 Főoldal"

# E.ON árak automatikus lekérése az alkalmazás indításakor
if 'loss_price' not in st.session_state or 'market_price' not in st.session_state:
    with st.spinner("E.ON árak automatikus lekérése..."):
        loss_price, market_price, error = scrape_eon_prices()
    
    if error:
        st.session_state.loss_price = None
        st.session_state.market_price = None
        st.session_state.eon_error = error
    else:
        st.session_state.loss_price = loss_price
        st.session_state.market_price = market_price
        st.session_state.eon_error = None

# Oldal változó
page = st.session_state.page

# Oldal megjelenítése
if page == "🏠 Főoldal":
    show_home_page()
elif page == "⚡ Energiafogyasztás és megtakarítás előrejelzés":
    show_energy_prediction_page()
elif page == "💰 Megtakarítások":
    show_savings_page()
