import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_services.api_call_CO2 import fetch_co2_emission_data

def show_co2_savings():
    """CO2 megtakarítások számítása és megjelenítése"""
    st.write("## CO2 megtakarítás számítása")
    
    # Tábla kiválasztása CO2 számításhoz
    col1, col2 = st.columns(2)
    
    with col1:
        table_options = {
            "dfv_smart_db": "Oksovezérlő",
            "dfv_termosztat_db": "Termosztátos vezérlő"
        }
        
        selected_table = st.selectbox(
            "Válassz táblát:",
            options=list(table_options.keys()),
            format_func=lambda x: table_options[x],
            key="co2_table_selector"
        )
    
    with col2:
        st.write("")
    
    heater_power = st.session_state.get('heater_power', None)
    
    if heater_power is None or heater_power <= 0:
        st.warning("⚠️ Kérjük, adjon meg egy érvényes hagyományos fűtőtest teljesítményt a navigációs sávban!")
    else:
        # CO2 adatok lekérése
        days_to_show = 10
        
        # API kulcs betöltése a Streamlit secrets-ből
        try:
            api_key = st.secrets["api"]["electricity_maps_token"]
        except (KeyError, FileNotFoundError) as e:
            st.error(f"Hiányzik a .streamlit/secrets.toml fájl vagy az API kulcs. Hiba: {e}")
            api_key = None
        
        # Session state inicializálása CO2 adatokhoz
        if 'co2_cached_days' not in st.session_state:
            st.session_state.co2_cached_days = 10
        if 'co2_cached_table' not in st.session_state:
            st.session_state.co2_cached_table = None
        if 'co2_cached_heater_power' not in st.session_state:
            st.session_state.co2_cached_heater_power = None
        
        # Ha változott a fűtőteljesítmény vagy a tábla, töröljük a cache-t
        current_heater_power = st.session_state.get('heater_power', None)
        if (st.session_state.co2_cached_heater_power != current_heater_power) or (st.session_state.co2_cached_table != selected_table):
            # Töröljük a CO2 cache-t, ha változott a fűtőteljesítmény vagy a tábla
            if 'co2_hourly_dataframe' in st.session_state:
                del st.session_state['co2_hourly_dataframe']
            if 'co2_hourly_with_power' in st.session_state:
                del st.session_state['co2_hourly_with_power']
            if 'co2_daily_dataframe' in st.session_state:
                del st.session_state['co2_daily_dataframe']
            if 'power_co2_pairs' in st.session_state:
                del st.session_state['power_co2_pairs']
            st.session_state.co2_cached_heater_power = current_heater_power
            st.session_state.co2_cached_table = selected_table
        
        auto_refresh = ('co2_hourly_dataframe' not in st.session_state) or (st.session_state.co2_cached_table != selected_table)
        
        if auto_refresh and api_key:
            with st.spinner("CO2 adatok lekérése folyamatban..."):
                result = fetch_co2_emission_data(days_to_show, api_key, selected_table, heater_power)
                
                if result and len(result) >= 3:
                    co2_hourly_df = result[0]
                    co2_hourly_with_power = result[1]
                    daily_co2_df = result[2]
                    power_co2_pairs = result[3] if len(result) > 3 else None
                    
                    if co2_hourly_df is not None:
                        # Adatok cache-elése
                        st.session_state['co2_hourly_dataframe'] = co2_hourly_df
                        st.session_state['co2_cached_days'] = days_to_show
                        st.session_state['co2_cached_table'] = selected_table
                        
                        if co2_hourly_with_power is not None and daily_co2_df is not None:
                            st.session_state['co2_hourly_with_power'] = co2_hourly_with_power
                            st.session_state['co2_daily_dataframe'] = daily_co2_df
                            if power_co2_pairs is not None:
                                st.session_state['power_co2_pairs'] = power_co2_pairs
        
        # CO2 megtakarítás számítása
        if 'co2_hourly_dataframe' in st.session_state and st.session_state['co2_hourly_dataframe'] is not None:
            co2_hourly_df = st.session_state['co2_hourly_dataframe']
            
            # A hagyományos fűtőtest konstans teljesítményével számolt CO2 kibocsátás
            # Minden órára: energia (kWh) = heater_power (W) * 1 óra / 1000
            # CO2 (g) = energia (kWh) * CO2 intenzitás (g CO2/kWh)
            
            # Órás energia számítása
            hourly_energy_kwh = heater_power / 1000.0  # 1 óra alatt
            
            # CO2 számítása minden órára
            co2_hourly_df_copy = co2_hourly_df.copy()
            co2_hourly_df_copy['Izzó_energia_kWh'] = hourly_energy_kwh
            co2_hourly_df_copy['Izzó_CO2_g'] = co2_hourly_df_copy['Izzó_energia_kWh'] * co2_hourly_df_copy['CO2 Kibocsátás (g CO2/kWh)']
            
            # Napi összesítés a hagyományos fűtőtest CO2 kibocsátására
            heater_daily_co2 = co2_hourly_df_copy.groupby('Dátum').agg({
                'Izzó_CO2_g': 'sum'
            }).reset_index()
            heater_daily_co2.columns = ['Dátum', 'Hagyományos fűtőtest napi CO2 (g)']
            
            # Összehasonlítás az adatbázisból lekért adatokkal
            if 'co2_daily_dataframe' in st.session_state and st.session_state['co2_daily_dataframe'] is not None:
                daily_co2_df = st.session_state['co2_daily_dataframe']
                
                # Összevonás dátum szerint
                comparison_df = pd.merge(
                    daily_co2_df[['Dátum', 'Napi CO2 (g)']],
                    heater_daily_co2,
                    on='Dátum',
                    how='inner'
                )
                
                # Megtakarítás számítása (Hagyományos fűtőtest CO2 - Adatbázis CO2)
                comparison_df['CO2 megtakarítás (g)'] = comparison_df['Hagyományos fűtőtest napi CO2 (g)'] - comparison_df['Napi CO2 (g)']
                comparison_df['Megtakarítás százalék'] = (comparison_df['CO2 megtakarítás (g)'] / comparison_df['Hagyományos fűtőtest napi CO2 (g)']) * 100
                
                # Összesített eredmények
                st.write("### Összesített eredmények")
                
                total_database_co2 = comparison_df['Napi CO2 (g)'].sum()
                total_heater_co2 = comparison_df['Hagyományos fűtőtest napi CO2 (g)'].sum()
                total_savings = comparison_df['CO2 megtakarítás (g)'].sum()
                avg_savings_percent = comparison_df['Megtakarítás százalék'].mean()
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Adatbázis összes CO2", f"{total_database_co2:.2f} g")
                with col2:
                    st.metric("Hagyományos fűtőtest összes CO2", f"{total_heater_co2:.2f} g")
                with col3:
                    st.metric("Összes megtakarítás", f"{total_savings:.2f} g", 
                             delta=f"{avg_savings_percent:.2f}%")
                with col4:
                    st.metric("Átlagos napi megtakarítás", f"{total_savings / len(comparison_df):.2f} g")
                
                # Részletes napi összehasonlítás táblázat
                st.write("### Részletes napi összehasonlítás")
                display_comparison = comparison_df[['Dátum', 'Napi CO2 (g)', 'Hagyományos fűtőtest napi CO2 (g)', 'CO2 megtakarítás (g)', 'Megtakarítás százalék']].copy()
                display_comparison.columns = ['Dátum', 'Adatbázis CO2 (g)', 'Hagyományos fűtőtest CO2 (g)', 'Megtakarítás (g)', 'Megtakarítás (%)']
                display_comparison = display_comparison.round(2)
                st.dataframe(display_comparison, use_container_width=True)
                
                # Vizuális összehasonlítás
                st.write("### Vizuális összehasonlítás")
                fig_comparison = go.Figure()
                
                fig_comparison.add_trace(go.Scatter(
                    x=comparison_df['Dátum'],
                    y=comparison_df['Napi CO2 (g)'],
                    mode='lines+markers',
                    name='Adatbázis CO2',
                    line=dict(color='blue', width=2),
                    marker=dict(size=6)
                ))
                
                fig_comparison.add_trace(go.Scatter(
                    x=comparison_df['Dátum'],
                    y=comparison_df['Hagyományos fűtőtest napi CO2 (g)'],
                    mode='lines+markers',
                    name='Hagyományos fűtőtest CO2',
                    line=dict(color='red', width=2, dash='dash'),
                    marker=dict(size=6)
                ))
                
                fig_comparison.update_layout(
                    title="CO2 Kibocsátás összehasonlítás: Adatbázis vs Hagyományos fűtőtest",
                    xaxis_title="Dátum",
                    yaxis_title="CO2 Kibocsátás (g)",
                    hovermode='x unified',
                    template="plotly_white",
                    height=500
                )
                
                st.plotly_chart(fig_comparison, use_container_width=True)
                
                # Megtakarítás grafikon
                fig_savings = go.Figure()
                
                fig_savings.add_trace(go.Bar(
                    x=comparison_df['Dátum'],
                    y=comparison_df['CO2 megtakarítás (g)'],
                    name='CO2 megtakarítás',
                    marker=dict(color='green')
                ))
                
                fig_savings.update_layout(
                    title="Napi CO2 Megtakarítás",
                    xaxis_title="Dátum",
                    yaxis_title="CO2 Megtakarítás (g)",
                    template="plotly_white",
                    height=400
                )
                
                st.plotly_chart(fig_savings, use_container_width=True)
                
            else:
                st.warning("Nincs elegendő adat az összehasonlításhoz. Kérjük, várjon, amíg a CO2 adatok betöltődnek.")
        else:
            st.warning("Nincs elegendő adat az összehasonlításhoz. Kérjük, várjon, amíg a CO2 adatok betöltődnek.")

