import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_services.eon_scraper import calculate_energy_costs
from app_services.database import execute_query

def show_consumption_cost_savings(start_date, end_date):
    """Fogyasztási és költség megtakarítások számítása és megjelenítése"""
    st.write("## Fogyasztási és költség megtakarítások")
    st.write("### Okosvezérlő és Termosztátos vezérlő összehasonlítás")
    
    if 'loss_price' in st.session_state and st.session_state.loss_price is not None:
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
                        smart_loss_cost, _ = calculate_energy_costs(
                            smart_avg, st.session_state.loss_price)
                        thermostat_loss_cost, _ = calculate_energy_costs(
                            thermostat_avg, st.session_state.loss_price)
                        
                        if smart_loss_cost is not None and thermostat_loss_cost is not None:
                            # Számított értékek
                            consumption_diff = smart_avg - thermostat_avg
                            cost_diff = smart_loss_cost - thermostat_loss_cost
                            monthly_diff = cost_diff * 30
                            yearly_diff = cost_diff * 365
                            
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
                                'Vezérlő típus': ['Okosvezérlő', 'Termosztátos vezérlő', 'Különbség'],
                                'Veszteségi ár költség (Ft/nap)': [
                                    f"{smart_loss_cost:.2f}", 
                                    f"{thermostat_loss_cost:.2f}",
                                    f"{cost_diff:+.2f}"
                                ]
                            }
                            
                            cost_df = pd.DataFrame(cost_data)
                            st.dataframe(
                                cost_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Vezérlő típus": st.column_config.TextColumn("Vezérlő típus", width="medium"),
                                    "Veszteségi ár költség (Ft/nap)": st.column_config.TextColumn("Veszteségi ár költség (Ft/nap)", width="medium")
                                }
                            )
                            
                            # Fogyasztási megtakarítás számítás
                            if consumption_diff < 0:
                                savings_w = abs(consumption_diff)
                                savings_kwh_day = savings_w / 1000.0
                                savings_kwh_month = savings_kwh_day * 30
                                savings_kwh_year = savings_kwh_day * 365
                                
                                st.write("### 💡 Fogyasztási megtakarítás")
                                
                                savings_data = {
                                    'Időszak': ['Napi', 'Havi', 'Éves'],
                                    'Megtakarítás (kWh)': [
                                        f"{savings_kwh_day:.2f}",
                                        f"{savings_kwh_month:.2f}",
                                        f"{savings_kwh_year:.2f}"
                                    ]
                                }
                                
                                savings_df = pd.DataFrame(savings_data)
                                st.dataframe(
                                    savings_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                        "Megtakarítás (kWh)": st.column_config.TextColumn("Megtakarítás (kWh)", width="medium")
                                    }
                                )
                            else:
                                st.info("Az Okosvezérlő átlagosan többet fogyaszt, mint a Termosztátos vezérlő ezen az időszakon.")
                            
                            # Költség különbség táblázat
                            st.write("### 📈 Költség különbség")
                            
                            cost_diff_data = {
                                'Időszak': ['Napi', 'Havi', 'Éves'],
                                'Különbség (Ft)': [
                                    f"{cost_diff:+.2f}",
                                    f"{monthly_diff:+.2f}",
                                    f"{yearly_diff:+.2f}"
                                ]
                            }
                            
                            cost_diff_df = pd.DataFrame(cost_diff_data)
                            st.dataframe(
                                cost_diff_df,
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
                                    'Napi költség különbség (Ft)',
                                    'Havi költség különbség (Ft)',
                                    'Éves költség különbség (Ft)'
                                ],
                                'Érték': [
                                    f"{consumption_diff:+.2f}",
                                    f"{cost_diff:+.2f}",
                                    f"{monthly_diff:+.2f}",
                                    f"{yearly_diff:+.2f}"
                                ],
                                'Jelentés': [
                                    "Okosvezérlő alacsonyabb fogyasztás" if consumption_diff < 0 else "Termosztátos vezérlő alacsonyabb fogyasztás",
                                    "Okosvezérlő alacsonyabb költség" if cost_diff < 0 else "Termosztátos vezérlő alacsonyabb költség",
                                    "Okosvezérlő alacsonyabb havi költség" if monthly_diff < 0 else "Termosztátos vezérlő alacsonyabb havi költség",
                                    "Okosvezérlő alacsonyabb éves költség" if yearly_diff < 0 else "Termosztátos vezérlő alacsonyabb éves költség"
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
                        else:
                            st.error("Nem sikerült kiszámítani a költségeket.")
                        
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
                        st.warning("Nincs elegendő adat az összehasonlításhoz!")
                        
                except Exception as e:
                    st.error(f"Hiba az összehasonlítás során: {e}")
    else:
        st.warning("⚠️ Az összehasonlításhoz szükségesek az E.ON árak!")

