import streamlit as st
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from page_modules.co2_savings_module import show_co2_savings
from page_modules.consumption_cost_savings_module import show_consumption_cost_savings

def show_savings_page():
    
    with open('styles.css', 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    st.markdown(f"""
    <style>
    {css_content}
    </style>
    """, unsafe_allow_html=True)
    
    st.write("# Megtakarítások")
    
    # E.ON árak státusz megjelenítése
    if 'loss_prices' in st.session_state and st.session_state.loss_prices is not None:
        st.success("✅ Árak elérhetők")
    elif 'eon_error' in st.session_state and st.session_state.eon_error:
        st.error(f"❌ E.ON árak lekérése sikertelen: {st.session_state.eon_error}")
    else:
        st.warning("⚠️ E.ON árak nem érhetők el")
    
    st.write("---")
    
    # Megtakarítás típus inicializálása session state-ben
    if "savings_type" not in st.session_state:
        st.session_state.savings_type = "CO2 megtakarítások"
    
    # Megtakarítás típus kiválasztása gombokkal
    st.write("## Megtakarítás típus kiválasztása")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("CO2 megtakarítások", use_container_width=True, 
                     type="primary" if st.session_state.savings_type == "CO2 megtakarítások" else "secondary"):
            st.session_state.savings_type = "CO2 megtakarítások"
            st.rerun()
    
    with col2:
        if st.button("Fogyasztási és költség megtakarítások", use_container_width=True,
                     type="primary" if st.session_state.savings_type == "Fogyasztási és költség megtakarítások" else "secondary"):
            st.session_state.savings_type = "Fogyasztási és költség megtakarítások"
            st.rerun()
    
    savings_type = st.session_state.savings_type
    
    st.write("---")
    
    # CO2 megtakarítások
    if savings_type == "CO2 megtakarítások":
        show_co2_savings()
    
    # Fogyasztási és költség megtakarítások
    elif savings_type == "Fogyasztási és költség megtakarítások":
        # Alapértelmezett dátumok használata
        start_date = datetime(2024, 8, 19).date()
        end_date = datetime(2025, 8, 21).date()
        show_consumption_cost_savings(start_date, end_date)
