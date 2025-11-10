import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_services.eon_scraper import calculate_energy_costs
from app_services.database import execute_query

def show_consumption_cost_savings(start_date, end_date):
    """Fogyasztási és költség megtakarítások számítása és megjelenítése"""
    st.write("## Fogyasztási és költség megtakarítások")
    
    if 'loss_prices' in st.session_state and st.session_state.loss_prices is not None:
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
                        
                        # Napi energia számítás
                        smart_daily_energy_df = smart_df.groupby('date')['value'].sum().reset_index()
                        smart_daily_energy_df.columns = ['date', 'daily_energy_kwh']
                        thermostat_daily_energy_df = thermostat_df.groupby('date')['value'].sum().reset_index()
                        thermostat_daily_energy_df.columns = ['date', 'daily_energy_kwh']
                        
                        smart_daily = smart_df.groupby('date')['value'].mean().reset_index()
                        thermostat_daily = thermostat_df.groupby('date')['value'].mean().reset_index()
                        
                        smart_daily['datetime'] = pd.to_datetime(smart_daily['date'])
                        thermostat_daily['datetime'] = pd.to_datetime(thermostat_daily['date'])
                        smart_daily_energy_df['datetime'] = pd.to_datetime(smart_daily_energy_df['date'])
                        thermostat_daily_energy_df['datetime'] = pd.to_datetime(thermostat_daily_energy_df['date'])
                        
                        # Veszteségi árak kinyerése dátum alapján
                        loss_prices = st.session_state.get('loss_prices', None)
                        if loss_prices:
                            try:
                                # 2024-es és 2025-ös árak kinyerése
                                price_2024_str = loss_prices.get('2024', '')
                                price_2025_str = loss_prices.get('2025', '')
                                
                                loss_price_2024 = float(price_2024_str.replace(',', '.').replace(' Ft/kWh', '')) if price_2024_str else None
                                loss_price_2025 = float(price_2025_str.replace(',', '.').replace(' Ft/kWh', '')) if price_2025_str else None
                            except:
                                loss_price_2024 = None
                                loss_price_2025 = None
                        else:
                            loss_price_2024 = None
                            loss_price_2025 = None
                        
                     
                        smart_daily_energy = smart_daily_energy_df['daily_energy_kwh'].mean()
                        thermostat_daily_energy = thermostat_daily_energy_df['daily_energy_kwh'].mean()
                        
                        # Működési órák számítása 
                        time_interval_hours = 0.25  # 15 perc = 0.25 óra
                        
                        # Számoljuk meg, hogy hány intervallumban futott a vezérlő (value > 0)
                        # Napi bontásban számoljuk
                        smart_daily_operating_intervals = smart_df.groupby('date').apply(
                            lambda x: (x['value'] > 0).sum()
                        ).mean()  # Átlagos napi működő intervallumok száma
                        
                        thermostat_daily_operating_intervals = thermostat_df.groupby('date').apply(
                            lambda x: (x['value'] > 0).sum()
                        ).mean()  # Átlagos napi működő intervallumok száma
                        
                        # Működési órák számítása
                        smart_operating_hours = smart_daily_operating_intervals * time_interval_hours
                        thermostat_operating_hours = thermostat_daily_operating_intervals * time_interval_hours
                        
                        # Átlagos napi fogyasztás W-ban számítása
                        # Teljesítmény (W) = (Energia (kWh) / Működési óra) * 1000
                        if smart_operating_hours > 0:
                            smart_avg = (smart_daily_energy / smart_operating_hours) * 1000  # W-ba konvertálva
                        else:
                            smart_avg = 0
                        
                        if thermostat_operating_hours > 0:
                            thermostat_avg = (thermostat_daily_energy / thermostat_operating_hours) * 1000  # W-ba konvertálva
                        else:
                            thermostat_avg = 0
                        
                        # Hagyományos fűtőtest: egyszerű számítás
                        heater_usage_hours = 24  # óra
                        heater_daily_energy = (heater_power * heater_usage_hours) / 1000.0  # kWh
                        # Hagyományos fűtőtest konstans teljesítménye (W)
                        heater_avg = heater_power
                        
                        # Veszteségi energiaár költségek számítása dátum alapján
                        # Költség = Napi energia (kWh) × Veszteségi ár (Ft/kWh)
                        # Dátum alapján választjuk ki a megfelelő árat (2024-es vagy 2025-ös)
                        if loss_price_2024 is not None and loss_price_2025 is not None:
                            # Átlagos napi költségek számítása - dátum alapján súlyozott átlag
                            # Számoljuk meg, hogy hány nap 2024-es és hány nap 2025-ös
                            smart_daily_energy_df['year'] = pd.to_datetime(smart_daily_energy_df['date']).dt.year
                            thermostat_daily_energy_df['year'] = pd.to_datetime(thermostat_daily_energy_df['date']).dt.year
                            
                            # 2024-es és 2025-ös napok száma
                            days_2024_smart = (smart_daily_energy_df['year'] == 2024).sum()
                            days_2025_smart = (smart_daily_energy_df['year'] == 2025).sum()
                            total_days_smart = len(smart_daily_energy_df)
                            
                            days_2024_thermo = (thermostat_daily_energy_df['year'] == 2024).sum()
                            days_2025_thermo = (thermostat_daily_energy_df['year'] == 2025).sum()
                            total_days_thermo = len(thermostat_daily_energy_df)
                            
                            # Súlyozott átlagos ár számítása
                            if total_days_smart > 0:
                                avg_price_smart = (days_2024_smart * loss_price_2024 + days_2025_smart * loss_price_2025) / total_days_smart
                            else:
                                avg_price_smart = loss_price_2025  # Alapértelmezett: 2025-ös ár
                            
                            if total_days_thermo > 0:
                                avg_price_thermo = (days_2024_thermo * loss_price_2024 + days_2025_thermo * loss_price_2025) / total_days_thermo
                            else:
                                avg_price_thermo = loss_price_2025  # Alapértelmezett: 2025-ös ár
                            
                            # Átlagos napi költségek számítása
                            smart_loss_cost = smart_daily_energy * avg_price_smart  # Ft/nap
                            thermostat_loss_cost = thermostat_daily_energy * avg_price_thermo  # Ft/nap
                            
                            # Hagyományos fűtőtest költsége - dátum alapján súlyozott átlag
                            # Feltételezzük, hogy ugyanaz az időszak
                            if total_days_smart > 0:
                                avg_price_heater = (days_2024_smart * loss_price_2024 + days_2025_smart * loss_price_2025) / total_days_smart
                            else:
                                avg_price_heater = loss_price_2025
                            
                            heater_loss_cost = heater_daily_energy * avg_price_heater  # Ft/nap
                            
                            # Megtakarítás számítása veszteségi energiaár alapján
                            # Megtakarítás = (Hagyományos napi energia - Okosvezérlő napi energia) × Veszteségi ár
                            smart_savings_energy = heater_daily_energy - smart_daily_energy  # kWh/nap
                            thermostat_savings_energy = heater_daily_energy - thermostat_daily_energy  # kWh/nap
                            
                            smart_savings_cost = smart_savings_energy * avg_price_smart  # Ft/nap
                            thermostat_savings_cost = thermostat_savings_energy * avg_price_thermo  # Ft/nap
                        else:
                            smart_loss_cost = None
                            thermostat_loss_cost = None
                            heater_loss_cost = None
                            smart_savings_cost = None
                            thermostat_savings_cost = None
                            smart_savings_energy = None
                            thermostat_savings_energy = None
                            avg_price_smart = None
                            avg_price_thermo = None
                            avg_price_heater = None
                        
                        if (smart_loss_cost is not None and thermostat_loss_cost is not None and heater_loss_cost is not None 
                            and smart_savings_cost is not None and thermostat_savings_cost is not None
                            and smart_savings_energy is not None and thermostat_savings_energy is not None):
                            # Számított értékek - Okosvezérlő vs Hagyományos fűtőtest
                            consumption_diff_smart_heater = smart_avg - heater_avg
                            # Megtakarítás pozitív értékben (ha negatív, akkor nincs megtakarítás)
                            cost_diff_smart_heater = -smart_savings_cost  # Negatív, mert megtakarítás
                            monthly_savings_smart = smart_savings_cost * 30
                            yearly_savings_smart = smart_savings_cost * 365
                            
                            # Számított értékek - Termosztátos vezérlő vs Hagyományos fűtőtest
                            consumption_diff_thermo_heater = thermostat_avg - heater_avg
                            # Megtakarítás pozitív értékben (ha negatív, akkor nincs megtakarítás)
                            cost_diff_thermo_heater = -thermostat_savings_cost  # Negatív, mert megtakarítás
                            monthly_savings_thermo = thermostat_savings_cost * 30
                            yearly_savings_thermo = thermostat_savings_cost * 365
                            
                            monthly_diff_smart_heater = cost_diff_smart_heater * 30
                            yearly_diff_smart_heater = cost_diff_smart_heater * 365
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
                            
                            # Veszteségi energiaár megtakarítás táblázat
                            st.write("### 💰 Veszteségi energiaár megtakarítás")
                            
                            # Okosvezérlő megtakarítás
                            if smart_savings_cost > 0:
                                st.write("#### Okosvezérlő vs Hagyományos fűtőtest")
                                savings_data_smart = {
                                    'Időszak': ['Napi', 'Havi', 'Éves'],
                                    'Energia megtakarítás (kWh)': [
                                        f"{smart_savings_energy:.2f}",
                                        f"{smart_savings_energy * 30:.2f}",
                                        f"{smart_savings_energy * 365:.2f}"
                                    ],
                                    'Pénzügyi megtakarítás (Ft)': [
                                        f"{smart_savings_cost:.2f}",
                                        f"{monthly_savings_smart:.2f}",
                                        f"{yearly_savings_smart:.2f}"
                                    ]
                                }
                                savings_df_smart = pd.DataFrame(savings_data_smart)
                                st.dataframe(
                                    savings_df_smart,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                        "Energia megtakarítás (kWh)": st.column_config.TextColumn("Energia megtakarítás (kWh)", width="medium"),
                                        "Pénzügyi megtakarítás (Ft)": st.column_config.TextColumn("Pénzügyi megtakarítás (Ft)", width="medium")
                                    }
                                )
                            else:
                                st.info("ℹ️ Az okosvezérlő nem takarít meg energiát a hagyományos fűtőtesthez képest.")
                            
                            # Termosztátos vezérlő megtakarítás
                            if thermostat_savings_cost > 0:
                                st.write("#### Termosztátos vezérlő vs Hagyományos fűtőtest")
                                savings_data_thermo = {
                                    'Időszak': ['Napi', 'Havi', 'Éves'],
                                    'Energia megtakarítás (kWh)': [
                                        f"{thermostat_savings_energy:.2f}",
                                        f"{thermostat_savings_energy * 30:.2f}",
                                        f"{thermostat_savings_energy * 365:.2f}"
                                    ],
                                    'Pénzügyi megtakarítás (Ft)': [
                                        f"{thermostat_savings_cost:.2f}",
                                        f"{monthly_savings_thermo:.2f}",
                                        f"{yearly_savings_thermo:.2f}"
                                    ]
                                }
                                savings_df_thermo = pd.DataFrame(savings_data_thermo)
                                st.dataframe(
                                    savings_df_thermo,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                        "Energia megtakarítás (kWh)": st.column_config.TextColumn("Energia megtakarítás (kWh)", width="medium"),
                                        "Pénzügyi megtakarítás (Ft)": st.column_config.TextColumn("Pénzügyi megtakarítás (Ft)", width="medium")
                                    }
                                )
                            else:
                                st.info("ℹ️ A termosztátos vezérlő nem takarít meg energiát a hagyományos fűtőtesthez képest.")
                            
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
                        
                        # Adatok előkészítése a korrelációs diagramokhoz
                        if len(smart_daily) > 0 and len(thermostat_daily) > 0:
                            time_interval_hours = 0.25  # 15 perc = 0.25 óra
                            
                            # Napi bontásban számoljuk a működési órákat és teljesítményt
                            smart_daily_operating_hours = smart_df.groupby('date').apply(
                                lambda x: (x['value'] > 0).sum() * time_interval_hours
                            )
                            thermostat_daily_operating_hours = thermostat_df.groupby('date').apply(
                                lambda x: (x['value'] > 0).sum() * time_interval_hours
                            )
                            
                            # Napi energia és teljesítmény számítása
                            smart_daily_energy_per_day = smart_df.groupby('date')['value'].sum()
                            thermostat_daily_energy_per_day = thermostat_df.groupby('date')['value'].sum()
                            
                            # Teljesítmény W-ban = (Energia kWh / Működési óra) * 1000
                            smart_daily_w = (smart_daily_energy_per_day / smart_daily_operating_hours.replace(0, 1)) * 1000
                            smart_daily_w = smart_daily_w.replace([np.inf, -np.inf], 0)
                            
                            thermostat_daily_w = (thermostat_daily_energy_per_day / thermostat_daily_operating_hours.replace(0, 1)) * 1000
                            thermostat_daily_w = thermostat_daily_w.replace([np.inf, -np.inf], 0)
                            
                            # DataFrame-ek létrehozása a grafikonhoz
                            smart_daily_w_df = pd.DataFrame({
                                'date': smart_daily_w.index,
                                'value': smart_daily_w.values
                            })
                            smart_daily_w_df['datetime'] = pd.to_datetime(smart_daily_w_df['date'])
                            
                            thermostat_daily_w_df = pd.DataFrame({
                                'date': thermostat_daily_w.index,
                                'value': thermostat_daily_w.values
                            })
                            thermostat_daily_w_df['datetime'] = pd.to_datetime(thermostat_daily_w_df['date'])
                            
                            # Fogyasztás-költség korrelációs diagramok
                            if loss_price_2024 is not None and loss_price_2025 is not None:
                                # Napi költségek számítása dátum alapján
                                # Dátum alapján választjuk ki a megfelelő árat
                                smart_daily_energy_df['year'] = pd.to_datetime(smart_daily_energy_df['date']).dt.year
                                thermostat_daily_energy_df['year'] = pd.to_datetime(thermostat_daily_energy_df['date']).dt.year
                                
                                # Napi költségek számítása - dátum alapján
                                smart_daily_energy_df['daily_cost_ft'] = smart_daily_energy_df.apply(
                                    lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                    axis=1
                                )
                                
                                thermostat_daily_energy_df['daily_cost_ft'] = thermostat_daily_energy_df.apply(
                                    lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                    axis=1
                                )
                                
                                # Hagyományos fűtőtest konstans költsége - átlagos árral
                                # Számoljuk újra az átlagos árat
                                days_2024_total = (smart_daily_energy_df['year'] == 2024).sum()
                                days_2025_total = (smart_daily_energy_df['year'] == 2025).sum()
                                total_days = len(smart_daily_energy_df)
                                
                                if total_days > 0:
                                    avg_price_heater = (days_2024_total * loss_price_2024 + days_2025_total * loss_price_2025) / total_days
                                else:
                                    avg_price_heater = loss_price_2025
                                
                                heater_daily_cost_constant = heater_daily_energy * avg_price_heater
                                
                                # Fogyasztás-költség korrelációs diagramok
                                st.write("### Fogyasztás-költség korreláció")
                                
                                # Fogyasztás W-ban és költség Ft-ban összekapcsolása
                                # Okosvezérlő adatok - összekapcsoljuk a helyes teljesítmény értékeket a költségekkel
                                smart_consumption_cost_df = smart_daily_w_df.merge(
                                    smart_daily_energy_df[['date', 'daily_cost_ft']], 
                                    on='date', 
                                    how='inner'
                                )
                                smart_consumption_cost_df.rename(columns={'value': 'fogyasztas_w', 'daily_cost_ft': 'koltseg_ft'}, inplace=True)
                                
                                # Termosztátos vezérlő adatok - összekapcsoljuk a helyes teljesítmény értékeket a költségekkel
                                thermostat_consumption_cost_df = thermostat_daily_w_df.merge(
                                    thermostat_daily_energy_df[['date', 'daily_cost_ft']], 
                                    on='date', 
                                    how='inner'
                                )
                                thermostat_consumption_cost_df.rename(columns={'value': 'fogyasztas_w', 'daily_cost_ft': 'koltseg_ft'}, inplace=True)
                                
                                # Két oszlopban jelenítjük meg a diagramokat
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    # 1. Okosvezérlő vs Hagyományos fűtőtest diagram
                                    st.write("#### Okosvezérlő vs Hagyományos fűtőtest")
                                    fig_scatter_smart = go.Figure()
                                    
                                    # Okosvezérlő pontok
                                    fig_scatter_smart.add_trace(go.Scatter(
                                        x=smart_consumption_cost_df['fogyasztas_w'],
                                        y=smart_consumption_cost_df['koltseg_ft'],
                                        mode='markers',
                                        name='Okosvezérlő',
                                        marker=dict(
                                            color='#00CC96',
                                            size=8,
                                            opacity=0.7,
                                            line=dict(width=1, color='#008060')
                                        ),
                                        text=[f"Dátum: {dt.strftime('%Y-%m-%d')}<br>Fogyasztás: {f:.2f} W<br>Költség: {k:.2f} Ft" 
                                              for dt, f, k in zip(smart_consumption_cost_df['datetime'], 
                                                                 smart_consumption_cost_df['fogyasztas_w'],
                                                                 smart_consumption_cost_df['koltseg_ft'])],
                                        hoverinfo='text'
                                    ))
                                    
                                    # Hagyományos fűtőtest referencia pont
                                    fig_scatter_smart.add_trace(go.Scatter(
                                        x=[heater_avg],
                                        y=[heater_daily_cost_constant],
                                        mode='markers',
                                        name='Hagyományos fűtőtest',
                                        marker=dict(
                                            color='gray',
                                            size=15,
                                            symbol='diamond',
                                            line=dict(width=2, color='black')
                                        ),
                                        text=f"Hagyományos fűtőtest<br>Fogyasztás: {heater_avg:.2f} W<br>Költség: {heater_daily_cost_constant:.2f} Ft",
                                        hoverinfo='text'
                                    ))
                                    
                                    # Okosvezérlő trendvonal
                                    if len(smart_consumption_cost_df) > 1:
                                        z_smart = np.polyfit(smart_consumption_cost_df['fogyasztas_w'], 
                                                            smart_consumption_cost_df['koltseg_ft'], 1)
                                        p_smart = np.poly1d(z_smart)
                                        x_trend_smart = np.linspace(smart_consumption_cost_df['fogyasztas_w'].min(), 
                                                                   smart_consumption_cost_df['fogyasztas_w'].max(), 100)
                                        fig_scatter_smart.add_trace(go.Scatter(
                                            x=x_trend_smart,
                                            y=p_smart(x_trend_smart),
                                            mode='lines',
                                            name='Okosvezérlő trendvonal',
                                            line=dict(color='white', width=4, dash='dot'),
                                            showlegend=True
                                        ))
                                    
                                    fig_scatter_smart.update_layout(
                                        xaxis_title="Fogyasztás (W)",
                                        yaxis_title="Költség (Ft)",
                                        hovermode='closest',
                                        template="plotly_white",
                                        height=500,
                                        title="Okosvezérlő vs Hagyományos fűtőtest",
                                        legend=dict(
                                            yanchor="top",
                                            y=0.99,
                                            xanchor="left",
                                            x=0.01
                                        )
                                    )
                                    
                                    st.plotly_chart(fig_scatter_smart, use_container_width=True)
                                
                                with col2:
                                    # 2. Termosztátos vezérlő vs Hagyományos fűtőtest diagram
                                    st.write("#### Termosztátos vezérlő vs Hagyományos fűtőtest")
                                    fig_scatter_thermo = go.Figure()
                                    
                                    # Termosztátos vezérlő pontok
                                    fig_scatter_thermo.add_trace(go.Scatter(
                                        x=thermostat_consumption_cost_df['fogyasztas_w'],
                                        y=thermostat_consumption_cost_df['koltseg_ft'],
                                        mode='markers',
                                        name='Termosztátos vezérlő',
                                        marker=dict(
                                            color='#636EFA',
                                            size=8,
                                            opacity=0.7,
                                            line=dict(width=1, color='#4040C0')
                                        ),
                                        text=[f"Dátum: {dt.strftime('%Y-%m-%d')}<br>Fogyasztás: {f:.2f} W<br>Költség: {k:.2f} Ft" 
                                              for dt, f, k in zip(thermostat_consumption_cost_df['datetime'], 
                                                                 thermostat_consumption_cost_df['fogyasztas_w'],
                                                                 thermostat_consumption_cost_df['koltseg_ft'])],
                                        hoverinfo='text'
                                    ))
                                    
                                    # Hagyományos fűtőtest referencia pont
                                    fig_scatter_thermo.add_trace(go.Scatter(
                                        x=[heater_avg],
                                        y=[heater_daily_cost_constant],
                                        mode='markers',
                                        name='Hagyományos fűtőtest',
                                        marker=dict(
                                            color='gray',
                                            size=15,
                                            symbol='diamond',
                                            line=dict(width=2, color='black')
                                        ),
                                        text=f"Hagyományos fűtőtest<br>Fogyasztás: {heater_avg:.2f} W<br>Költség: {heater_daily_cost_constant:.2f} Ft",
                                        hoverinfo='text'
                                    ))
                                    
                                    # Termosztátos vezérlő trendvonal
                                    if len(thermostat_consumption_cost_df) > 1:
                                        z_thermo = np.polyfit(thermostat_consumption_cost_df['fogyasztas_w'], 
                                                             thermostat_consumption_cost_df['koltseg_ft'], 1)
                                        p_thermo = np.poly1d(z_thermo)
                                        x_trend_thermo = np.linspace(thermostat_consumption_cost_df['fogyasztas_w'].min(), 
                                                                    thermostat_consumption_cost_df['fogyasztas_w'].max(), 100)
                                        fig_scatter_thermo.add_trace(go.Scatter(
                                            x=x_trend_thermo,
                                            y=p_thermo(x_trend_thermo),
                                            mode='lines',
                                            name='Termosztátos vezérlő trendvonal',
                                            line=dict(color='white', width=4, dash='dot'),
                                            showlegend=True
                                        ))
                                    
                                    fig_scatter_thermo.update_layout(
                                        xaxis_title="Fogyasztás (W)",
                                        yaxis_title="Költség (Ft)",
                                        hovermode='closest',
                                template="plotly_white",
                                height=500,
                                        title="Termosztátos vezérlő vs Hagyományos fűtőtest",
                                        legend=dict(
                                            yanchor="top",
                                            y=0.99,
                                            xanchor="left",
                                            x=0.01
                                        )
                                    )
                                    
                                    st.plotly_chart(fig_scatter_thermo, use_container_width=True)
                    
                    else:
                        st.warning("Nincs elegendő adat az összehasonlításhoz!")
                        
                except Exception as e:
                    st.error(f"Hiba az összehasonlítás során: {e}")
    else:
        st.warning("⚠️ Az összehasonlításhoz szükségesek az E.ON árak!")

