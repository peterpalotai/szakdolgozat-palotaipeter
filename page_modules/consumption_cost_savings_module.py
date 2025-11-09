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
    
    if 'loss_price' in st.session_state and st.session_state.loss_price is not None:
        heater_power = st.session_state.get('heater_power', None)
        
        if heater_power is None or heater_power <= 0:
            st.warning("⚠️ Kérjük, adjon meg egy érvényes hagyományos fűtőtest teljesítményt a navigációs sávban!")
        else:
            with st.spinner("Összehasonlítás számítása..."):
                try:
                    # Okosvezérlő adatainak lekérése
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
                    
                    # Termosztátos vezérlő adatainak lekérése
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
                        # Hagyományos fűtőtest konstans teljesítménye (W)
                        heater_avg = heater_power
                        
                        # Veszteségi ár kinyerése
                        try:
                            loss_price_num = float(st.session_state.loss_price.replace(',', '.').replace(' Ft/kWh', ''))
                        except:
                            loss_price_num = None
                        
                        # Pontosabb költség számítás órás adatokból
                        # Okosvezérlő és Termosztátos vezérlő: órás energia = teljesítmény (W) / 1000 * (időtartam órában)
                        # Feltételezzük, hogy 15 perces bontásban vannak az adatok
                        time_interval_hours = 0.25  # 15 perc = 0.25 óra
                        
                        # Napi energia összesítés
                        smart_daily_energy = smart_df.groupby('date').apply(
                            lambda x: ((x['value'] / 1000.0) * time_interval_hours).sum()
                        ).mean()  # Átlagos napi energia kWh-ban
                        
                        thermostat_daily_energy = thermostat_df.groupby('date').apply(
                            lambda x: ((x['value'] / 1000.0) * time_interval_hours).sum()
                        ).mean()  # Átlagos napi energia kWh-ban
                        
                        # Hagyományos fűtőtest: konstans teljesítmény 24 órán át
                        heater_daily_energy = (heater_power / 1000.0) * 24  # kWh
                        
                        # Költségek számítása
                        if loss_price_num is not None:
                            smart_loss_cost = smart_daily_energy * loss_price_num  # Ft/nap
                            thermostat_loss_cost = thermostat_daily_energy * loss_price_num  # Ft/nap
                            heater_loss_cost = heater_daily_energy * loss_price_num  # Ft/nap
                        else:
                            smart_loss_cost = None
                            thermostat_loss_cost = None
                            heater_loss_cost = None
                        
                        if smart_loss_cost is not None and thermostat_loss_cost is not None and heater_loss_cost is not None:
                            # Számított értékek - Okosvezérlő vs Hagyományos fűtőtest
                            consumption_diff_smart_heater = smart_avg - heater_avg
                            cost_diff_smart_heater = smart_loss_cost - heater_loss_cost
                            monthly_diff_smart_heater = cost_diff_smart_heater * 30
                            yearly_diff_smart_heater = cost_diff_smart_heater * 365
                            
                            # Számított értékek - Termosztátos vezérlő vs Hagyományos fűtőtest
                            consumption_diff_thermo_heater = thermostat_avg - heater_avg
                            cost_diff_thermo_heater = thermostat_loss_cost - heater_loss_cost
                            monthly_diff_thermo_heater = cost_diff_thermo_heater * 30
                            yearly_diff_thermo_heater = cost_diff_thermo_heater * 365
                            
                            # Összehasonlítás táblázatos megjelenítése
                            st.write("### 📊 Összehasonlítás eredmények")
                            
                            # Fogyasztás összehasonlítás táblázat
                            consumption_data = {
                                'Vezérlő típus': ['Okosvezérlő', 'Termosztátos vezérlő', 'Hagyományos fűtőtest'],
                                'Átlagos napi fogyasztás (W)': [
                                    f"{smart_avg:.2f}",
                                    f"{thermostat_avg:.2f}",
                                    f"{heater_avg:.2f}"
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
                                'Vezérlő típus': ['Okosvezérlő', 'Termosztátos vezérlő', 'Hagyományos fűtőtest'],
                                'Veszteségi ár költség (Ft/nap)': [
                                    f"{smart_loss_cost:.2f}",
                                    f"{thermostat_loss_cost:.2f}", 
                                    f"{heater_loss_cost:.2f}"
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
                            st.write("### 💡 Fogyasztási megtakarítás")
                            
                            # Okosvezérlő vs Hagyományos fűtőtest
                            if consumption_diff_smart_heater < 0:
                                savings_w = abs(consumption_diff_smart_heater)
                                # Napi átlagos fogyasztás különbség W-ban
                                savings_w_day = savings_w
                                # Havi átlagos fogyasztás különbség W-ban (napi átlag * 30)
                                savings_w_month = savings_w * 30
                                # Éves átlagos fogyasztás különbség W-ban (napi átlag * 365)
                                savings_w_year = savings_w * 365
                                
                                st.write("#### Okosvezérlő vs Hagyományos fűtőtest")
                                savings_data_smart_heater = {
                                    'Időszak': ['Napi', 'Havi', 'Éves'],
                                    'Megtakarítás (W)': [
                                        f"{savings_w_day:.2f}",
                                        f"{savings_w_month:.2f}",
                                        f"{savings_w_year:.2f}"
                                    ]
                                }
                                savings_df_smart_heater = pd.DataFrame(savings_data_smart_heater)
                                st.dataframe(
                                    savings_df_smart_heater,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                        "Megtakarítás (W)": st.column_config.TextColumn("Megtakarítás (W)", width="medium")
                                    }
                                )
                            
                            # Termosztátos vezérlő vs Hagyományos fűtőtest
                            if consumption_diff_thermo_heater < 0:
                                savings_w = abs(consumption_diff_thermo_heater)
                                # Napi átlagos fogyasztás különbség W-ban
                                savings_w_day = savings_w
                                # Havi átlagos fogyasztás különbség W-ban (napi átlag * 30)
                                savings_w_month = savings_w * 30
                                # Éves átlagos fogyasztás különbség W-ban (napi átlag * 365)
                                savings_w_year = savings_w * 365
                                
                                st.write("#### Termosztátos vezérlő vs Hagyományos fűtőtest")
                                savings_data_thermo_heater = {
                                    'Időszak': ['Napi', 'Havi', 'Éves'],
                                    'Megtakarítás (W)': [
                                        f"{savings_w_day:.2f}",
                                        f"{savings_w_month:.2f}",
                                        f"{savings_w_year:.2f}"
                                    ]
                                }
                                savings_df_thermo_heater = pd.DataFrame(savings_data_thermo_heater)
                                st.dataframe(
                                    savings_df_thermo_heater,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                        "Megtakarítás (W)": st.column_config.TextColumn("Megtakarítás (W)", width="medium")
                                    }
                                )
                            
                            # Költség különbség táblázat
                            st.write("### 📈 Költség különbség")
                            
                            # Okosvezérlő vs Hagyományos fűtőtest
                            st.write("#### Okosvezérlő vs Hagyományos fűtőtest")
                            cost_diff_data_smart_heater = {
                                'Időszak': ['Napi', 'Havi', 'Éves'],
                                'Különbség (Ft)': [
                                    f"{cost_diff_smart_heater:+.2f}",
                                    f"{monthly_diff_smart_heater:+.2f}",
                                    f"{yearly_diff_smart_heater:+.2f}"
                                ]
                            }
                            
                            cost_diff_df_smart_heater = pd.DataFrame(cost_diff_data_smart_heater)
                            st.dataframe(
                                cost_diff_df_smart_heater,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                    "Különbség (Ft)": st.column_config.TextColumn("Különbség (Ft)", width="medium")
                                }
                            )
                            
                            # Termosztátos vezérlő vs Hagyományos fűtőtest
                            st.write("#### Termosztátos vezérlő vs Hagyományos fűtőtest")
                            cost_diff_data_thermo_heater = {
                                'Időszak': ['Napi', 'Havi', 'Éves'],
                                'Különbség (Ft)': [
                                    f"{cost_diff_thermo_heater:+.2f}",
                                    f"{monthly_diff_thermo_heater:+.2f}",
                                    f"{yearly_diff_thermo_heater:+.2f}"
                                ]
                            }
                            
                            cost_diff_df_thermo_heater = pd.DataFrame(cost_diff_data_thermo_heater)
                            st.dataframe(
                                cost_diff_df_thermo_heater,
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
                                'Összehasonlítás': [
                                    'Okosvezérlő vs Hagyományos fűtőtest',
                                    'Termosztátos vezérlő vs Hagyományos fűtőtest'
                                ],
                                'Fogyasztás különbség (W)': [
                                    f"{consumption_diff_smart_heater:+.2f}",
                                    f"{consumption_diff_thermo_heater:+.2f}"
                                ],
                                'Napi költség különbség (Ft)': [
                                    f"{cost_diff_smart_heater:+.2f}",
                                    f"{cost_diff_thermo_heater:+.2f}"
                                ],
                                'Havi költség különbség (Ft)': [
                                    f"{monthly_diff_smart_heater:+.2f}",
                                    f"{monthly_diff_thermo_heater:+.2f}"
                                ],
                                'Éves költség különbség (Ft)': [
                                    f"{yearly_diff_smart_heater:+.2f}",
                                    f"{yearly_diff_thermo_heater:+.2f}"
                                ]
                            }
                            
                            summary_df = pd.DataFrame(summary_data)
                            st.dataframe(
                                summary_df,
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.error("Nem sikerült kiszámítani a költségeket.")
                        
                        # Vizualizáció
                        st.write("### Fogyasztás és költség vizualizáció")
                        
                        if len(smart_daily) > 0 and len(thermostat_daily) > 0:
                            # Összehasonlítás grafikon
                            fig_comparison = go.Figure()
                            
                            fig_comparison.add_trace(go.Scatter(
                                x=smart_daily['datetime'],
                                y=smart_daily['value'],
                                mode='lines+markers',
                                name='Okosvezérlő',
                                line=dict(color='#EA1C0A', width=2),
                                marker=dict(size=4)
                            ))
                            
                            fig_comparison.add_trace(go.Scatter(
                                x=thermostat_daily['datetime'],
                                y=thermostat_daily['value'],
                                mode='lines+markers',
                                name='Termosztátos vezérlő',
                                line=dict(color='blue', width=2),
                                marker=dict(size=4)
                            ))
                            
                            # Hagyományos fűtőtest konstans értéke
                            fig_comparison.add_hline(
                                y=heater_power,
                                line_dash="dash",
                                line_color="gray",
                                annotation_text="Hagyományos fűtőtest",
                                annotation_position="right"
                            )
                            
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

