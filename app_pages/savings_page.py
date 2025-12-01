import streamlit as st
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from page_modules.co2_savings_module import show_co2_savings
from page_modules.consumption_cost_savings_module import show_consumption_cost_savings

DEFAULT_START_DATE = datetime(2024, 8, 19).date()
DEFAULT_END_DATE = datetime(2025, 8, 21).date()

    
"CSS fájl betöltése."
def _load_css():
    try:
        with open('styles.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass
    
    
"E.ON árak státusz megjelenítése."
def _display_eon_status():
    if 'loss_prices' in st.session_state and st.session_state.loss_prices is not None:
        st.success("✅ Elérhető árak naprakészek")
    elif 'eon_error' in st.session_state and st.session_state.eon_error:
        st.error(f"❌ E.ON árak lekérése sikertelen: {st.session_state.eon_error}")
    else:
        st.warning("⚠️ E.ON árak nem érhetők el")
    
    
"Megtakarítás típus session state inicializálása."
def _initialize_savings_type():
    if "savings_type" not in st.session_state:
        st.session_state.savings_type = "CO2 megtakarítások"
    

"Megtakarítás típus kiválasztó gombok megjelenítése."
def _display_savings_type_selection():
    st.write("## Megtakarítás típus kiválasztása")
    col1, col2 = st.columns(2)
    
    with col1:
        is_co2_selected = st.session_state.savings_type == "CO2 megtakarítások"
        if st.button("CO2 megtakarítások", use_container_width=True, 
                    type="primary" if is_co2_selected else "secondary"):
            st.session_state.savings_type = "CO2 megtakarítások"
            st.rerun()
    
    with col2:
        is_cost_selected = st.session_state.savings_type == "Fogyasztási és költség megtakarítások"
        if st.button("Fogyasztási és költség megtakarítások", use_container_width=True,
                    type="primary" if is_cost_selected else "secondary"):
            st.session_state.savings_type = "Fogyasztási és költség megtakarítások"
            st.rerun()
    

"Megfelelő megtakarítás modul megjelenítése."
def _display_savings_content():
    savings_type = st.session_state.savings_type
    
    if savings_type == "CO2 megtakarítások":
        show_co2_savings()
    elif savings_type == "Fogyasztási és költség megtakarítások":
        show_consumption_cost_savings(DEFAULT_START_DATE, DEFAULT_END_DATE)


"Megtakarítások oldal megjelenítése."
def show_savings_page():
    _load_css()
    st.write("# Megtakarítások")
    
    _display_eon_status()
    st.write("---")
    
    _initialize_savings_type()
    _display_savings_type_selection()
    
    st.write("---")
    _display_savings_content()
