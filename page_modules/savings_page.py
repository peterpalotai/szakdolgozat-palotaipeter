import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from app_services.eon_scraper import calculate_energy_costs
from app_services.database import execute_query

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
    if 'loss_price' in st.session_state and 'market_price' in st.session_state and st.session_state.loss_price is not None:
        st.success("✅ Árak elérhetők")
    elif 'eon_error' in st.session_state and st.session_state.eon_error:
        st.error(f"❌ E.ON árak lekérése sikertelen: {st.session_state.eon_error}")
    else:
        st.warning("⚠️ E.ON árak nem érhetők el")
    
    st.write("---")
    
    # Időintervallum beállítása
    st.write("## Időintervallum beállítása")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Kezdő dátum
        start_date = st.date_input(
            "Kezdő dátum:",
            value=datetime(2024, 8, 19),
            key="comparison_start_date"
        )
    
    with col2:
        # Befejező dátum
        end_date = st.date_input(
            "Befejező dátum:",
            value=datetime(2025, 8, 21),
            key="comparison_end_date"
        )
    
    # Okosvezérlő vs Termosztátos vezérlő összehasonlítás
    if 'loss_price' in st.session_state and 'market_price' in st.session_state and st.session_state.loss_price is not None:
        st.write("---")
        st.write("## Okosvezérlő és Termosztátos vezérlő összehasonlítás")
        
        if st.button("Összehasonlítás generálása", type="primary"):
            with st.spinner("Összehasonlítás számítása..."):
                try:
                    # Mindkét tábla adatainak lekérése
                    smart_query = f"""
                    SELECT date, time, 
                           trend_smart_p as value,
                           trend_smart_i1 as current,
                           trend_smart_t as internal_temp,
                           trend_kulso_homerseklet_pillanatnyi as external_temp,
                           trend_smart_rh as internal_humidity,
                           trend_kulso_paratartalom as external_humidity
                    FROM dfv_smart_db
                    WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
                    AND trend_smart_p IS NOT NULL 
                    AND trend_smart_i1 IS NOT NULL
                    AND trend_smart_t IS NOT NULL
                    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                    ORDER BY date, time
                    """
                    
                    thermostat_query = f"""
                    SELECT date, time, 
                           trend_termosztat_p as value,
                           trend_termosztat_i1 as current,
                           trend_termosztat_t as internal_temp,
                           trend_kulso_homerseklet_pillanatnyi as external_temp,
                           trend_termosztat_rh as internal_humidity,
                           trend_kulso_paratartalom as external_humidity
                    FROM dfv_termosztat_db
                    WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
                    AND trend_termosztat_p IS NOT NULL 
                    AND trend_termosztat_i1 IS NOT NULL
                    AND trend_termosztat_t IS NOT NULL
                    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                    ORDER BY date, time
                    """
                    
                    smart_data = execute_query(smart_query)
                    thermostat_data = execute_query(thermostat_query)
                    
                    if smart_data and thermostat_data and len(smart_data) > 0 and len(thermostat_data) > 0:
                        # DataFrame-ek létrehozása
                        smart_df = pd.DataFrame(smart_data, columns=['date', 'time', 'value', 'current', 
                                                                    'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
                        thermostat_df = pd.DataFrame(thermostat_data, columns=['date', 'time', 'value', 'current', 
                                                                              'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
                        
                        # Dátum-idő kombinálása
                        smart_df['datetime'] = pd.to_datetime(smart_df['date'].astype(str) + ' ' + smart_df['time'].astype(str))
                        thermostat_df['datetime'] = pd.to_datetime(thermostat_df['date'].astype(str) + ' ' + thermostat_df['time'].astype(str))
                        
                        # Numerikus értékek konvertálása
                        smart_df['value'] = pd.to_numeric(smart_df['value'], errors='coerce')
                        thermostat_df['value'] = pd.to_numeric(thermostat_df['value'], errors='coerce')
                        
                        # Hiányzó értékek eltávolítása
                        smart_df = smart_df.dropna(subset=['value'])
                        thermostat_df = thermostat_df.dropna(subset=['value'])
                        
                        # Napi átlagolás
                        smart_df['date'] = smart_df['datetime'].dt.date
                        thermostat_df['date'] = thermostat_df['datetime'].dt.date
                        
                        smart_daily = smart_df.groupby('date')['value'].mean().reset_index()
                        thermostat_daily = thermostat_df.groupby('date')['value'].mean().reset_index()
                        
                        smart_daily['datetime'] = pd.to_datetime(smart_daily['date'])
                        thermostat_daily['datetime'] = pd.to_datetime(thermostat_daily['date'])
                        
                        # Átlagos napi fogyasztás
                        smart_avg = smart_daily['value'].mean()
                        thermostat_avg = thermostat_daily['value'].mean()
                        
                        # Költségek számítása
                        smart_loss_cost, smart_market_cost, _, _ = calculate_energy_costs(
                            smart_avg, st.session_state.loss_price, st.session_state.market_price)
                        thermostat_loss_cost, thermostat_market_cost, _, _ = calculate_energy_costs(
                            thermostat_avg, st.session_state.loss_price, st.session_state.market_price)
                        
                        if smart_loss_cost is not None and thermostat_loss_cost is not None:
                            # Megtakarítás számítás
                            smart_savings = smart_loss_cost - smart_market_cost
                            thermostat_savings = thermostat_loss_cost - thermostat_market_cost
                            savings_difference = smart_savings - thermostat_savings
                            
                            # Számított értékek
                            consumption_diff = smart_avg - thermostat_avg
                            monthly_diff = savings_difference * 30
                            yearly_diff = savings_difference * 365
                            
                            # Összehasonlítás táblázatos megjelenítése
                            st.write("### 📊 Összehasonlítás eredmények")
                            
                            # Fogyasztás összehasonlítás táblázat
                            consumption_data = {
                                'Vezérlő típus': ['Okosvezérlő', 'Termosztátos vezérlő', 'Különbség'],
                                'Átlagos napi fogyasztás (W)': [
                                    f"{smart_avg:.2f}",
                                    f"{thermostat_avg:.2f}",
                                    f"{consumption_diff:+.2f}"
                                ]
                            }
                            
                            consumption_df = pd.DataFrame(consumption_data)
                            st.dataframe(
                                consumption_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Vezérlő típus": st.column_config.TextColumn("Vezérlő típus", width="medium"),
                                    "Átlagos napi fogyasztás (W)": st.column_config.TextColumn("Átlagos napi fogyasztás (W)", width="large")
                                }
                            )
                            
                            # Költség összehasonlítás táblázat
                            st.write("### 💰 Költség összehasonlítás")
                            
                            cost_data = {
                                'Vezérlő típus': ['Okosvezérlő', 'Termosztátos vezérlő'],
                                'Veszteségi ár költség (Ft/nap)': [f"{smart_loss_cost:.2f}", f"{thermostat_loss_cost:.2f}"],
                                'Beszerzési ár költség (Ft/nap)': [f"{smart_market_cost:.2f}", f"{thermostat_market_cost:.2f}"],
                                'Napi megtakarítás (Ft)': [f"{smart_savings:.2f}", f"{thermostat_savings:.2f}"]
                            }
                            
                            cost_df = pd.DataFrame(cost_data)
                            st.dataframe(
                                cost_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Vezérlő típus": st.column_config.TextColumn("Vezérlő típus", width="medium"),
                                    "Veszteségi ár költség (Ft/nap)": st.column_config.TextColumn("Veszteségi ár költség (Ft/nap)", width="medium"),
                                    "Beszerzési ár költség (Ft/nap)": st.column_config.TextColumn("Beszerzési ár költség (Ft/nap)", width="medium"),
                                    "Napi megtakarítás (Ft)": st.column_config.TextColumn("Napi megtakarítás (Ft)", width="medium")
                                }
                            )
                            
                            # Megtakarítás különbség táblázat
                            st.write("### 📈 Megtakarítás különbség")
                            
                            savings_data = {
                                'Időszak': ['Napi', 'Havi', 'Éves'],
                                'Különbség (Ft)': [
                                    f"{savings_difference:+.2f}",
                                    f"{monthly_diff:+.2f}",
                                    f"{yearly_diff:+.2f}"
                                ]
                            }
                            
                            savings_df = pd.DataFrame(savings_data)
                            st.dataframe(
                                savings_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                    "Különbség (Ft)": st.column_config.TextColumn("Különbség (Ft)", width="medium")
                                }
                            )
                            
                            # Összefoglaló táblázat
                            st.write("### 📋 Összefoglaló")
                            
                            summary_data = {
                                'Mutató': [
                                    'Fogyasztás különbség (W)',
                                    'Napi megtakarítás különbség (Ft)',
                                    'Havi megtakarítás különbség (Ft)',
                                    'Éves megtakarítás különbség (Ft)'
                                ],
                                'Érték': [
                                    f"{consumption_diff:+.2f}",
                                    f"{savings_difference:+.2f}",
                                    f"{monthly_diff:+.2f}",
                                    f"{yearly_diff:+.2f}"
                                ],
                                'Jelentés': [
                                    "Okosvezérlő alacsonyabb fogyasztás" if consumption_diff < 0 else "Termosztátos vezérlő alacsonyabb fogyasztás",
                                    "Okosvezérlő több megtakarítás" if savings_difference > 0 else "Termosztátos vezérlő több megtakarítás",
                                    "Okosvezérlő több havi megtakarítás" if monthly_diff > 0 else "Termosztátos vezérlő több havi megtakarítás",
                                    "Okosvezérlő több éves megtakarítás" if yearly_diff > 0 else "Termosztátos vezérlő több éves megtakarítás"
                                ]
                            }
                            
                            summary_df = pd.DataFrame(summary_data)
                            st.dataframe(
                                summary_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Mutató": st.column_config.TextColumn("Mutató", width="large"),
                                    "Érték": st.column_config.TextColumn("Érték", width="medium"),
                                    "Jelentés": st.column_config.TextColumn("Jelentés", width="large")
                                }
                            )
                            
                            # Vizualizáció
                            st.write("### Fogyasztás és költség vizualizáció")
                            
                            # Közös dátumok meghatározása
                            common_dates = set(smart_daily['date']).intersection(set(thermostat_daily['date']))
                            common_dates = sorted(list(common_dates))
                            
                            if len(common_dates) > 0:
                                # Közös dátumokra szűrés
                                smart_common = smart_daily[smart_daily['date'].isin(common_dates)].sort_values('date')
                                thermostat_common = thermostat_daily[thermostat_daily['date'].isin(common_dates)].sort_values('date')
                                
                                # Összehasonlítás grafikon
                                fig_comparison = go.Figure()
                                
                                fig_comparison.add_trace(go.Scatter(
                                    x=smart_common['datetime'],
                                    y=smart_common['value'],
                                    mode='lines+markers',
                                    name='Okosvezérlő',
                                    line=dict(color='blue', width=2),
                                    marker=dict(size=4)
                                ))
                                
                                fig_comparison.add_trace(go.Scatter(
                                    x=thermostat_common['datetime'],
                                    y=thermostat_common['value'],
                                    mode='lines+markers',
                                    name='Termosztátos vezérlő',
                                    line=dict(color='red', width=2),
                                    marker=dict(size=4)
                                ))
                                
                                fig_comparison.update_layout(
                                    xaxis_title="Dátum",
                                    yaxis_title="Napi átlagos fogyasztás (W)",
                                    hovermode='x unified',
                                    template="plotly_white",
                                    height=500,
                                    title="Okosvezérlő és Termosztátos vezérlő fogyasztás összehasonlítás"
                                )
                                
                                st.plotly_chart(fig_comparison, use_container_width=True)
                        
                        else:
                            st.error("Nem sikerült kiszámítani a költségeket.")
                    
                    else:
                        st.warning("Nincs elegendő adat az összehasonlításhoz!")
                        
                except Exception as e:
                    st.error(f"Hiba az összehasonlítás során: {e}")
    
    else:
        st.warning("⚠️ Az összehasonlításhoz szükségesek az E.ON árak!")
