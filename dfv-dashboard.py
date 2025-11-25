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

# Fűtőteljesítmény és beruházás input csak a Megtakarítások oldalon
if st.session_state.page == "Megtakarítások":
    st.sidebar.write("### Fűtőteljesítmény beállítása")
    if 'heater_power' not in st.session_state:
        st.session_state.heater_power = 60.0  

    heater_power = st.sidebar.number_input(
        "Beépített fűtőteljesítmény (W):",
        min_value=30.0,
        max_value=120.0,
        value=st.session_state.heater_power,
        step=50.0,
        key="heater_power_input",
        help="A fűtőteljesítmény 30 és 120 W között mozoghat."
    )

    st.session_state.heater_power = heater_power
    

    if 'investment_cost' not in st.session_state:
        st.session_state.investment_cost = 0.0
    
    investment_cost = st.sidebar.number_input(
        "Beruházási költség (Ft):",
        min_value=0.0,
        value=st.session_state.investment_cost,
        step=1000.0,
        key="investment_cost_input",
        help="A dinamikus fűtésvezérlő beruházási költsége forintban."
    )
    
    st.session_state.investment_cost = investment_cost
    
    # Érzékenységvizsgálat ár változások input
    st.sidebar.write("### Érzékenységvizsgálat beállítások")
    
    if 'sensitivity_price_changes' not in st.session_state:
        st.session_state.sensitivity_price_changes = "-75,-50,-20,-10,0,10,20,50,75,100,200,300"
    
    # Input letiltva, ha nincs beruházási költség
    is_disabled = investment_cost <= 0
    
    sensitivity_price_changes = st.sidebar.text_input(
        "Ár változások (%):",
        value=st.session_state.sensitivity_price_changes,
        help="Vesszővel elválasztott értékek (pl: -75,-50,-20,-10,0,10,20,50,75,100,200,300). Az energiaár változásait százalékban adja meg.",
        key="sensitivity_price_changes_input",
        disabled=is_disabled
    )
    
    if not is_disabled:
        st.session_state.sensitivity_price_changes = sensitivity_price_changes
    else:
        st.sidebar.info("⚠️ Adja meg a beruházási költséget az érzékenységvizsgálat használatához.")

# E.ON árak automatikus lekérése az alkalmazás indításakor
if 'loss_prices' not in st.session_state:
    with st.spinner("E.ON árak automatikus lekérése..."):
        loss_prices, error = scrape_eon_prices()
    
    if error:
        st.session_state.loss_prices = None
        st.session_state.eon_error = error
    else:
        st.session_state.loss_prices = loss_prices 
        st.session_state.eon_error = None
        
        if loss_prices and '2025' in loss_prices:
            st.session_state.loss_price = loss_prices['2025']

# Oldal változó
page = st.session_state.page

# Oldal megjelenítése
if page == "Főoldal":
    show_home_page()
elif page == "Energiafogyasztás és megtakarítás előrejelzés":
    show_energy_prediction_page()
elif page == "Megtakarítások":
    show_savings_page()
