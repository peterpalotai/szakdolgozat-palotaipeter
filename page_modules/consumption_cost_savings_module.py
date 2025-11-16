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
from page_modules.database_queries import get_smart_controller_data, get_thermostat_controller_data

def show_consumption_cost_savings(start_date, end_date):
    """Fogyasztási és költség megtakarítások számítása és megjelenítése"""
    st.write("## Fogyasztási és költség megtakarítások")
    
    if 'loss_prices' in st.session_state and st.session_state.loss_prices is not None:
        heater_power = st.session_state.get('heater_power', None)
        
        if heater_power is None or heater_power <= 0:
            st.warning("Kérjük, adjon meg egy érvényes beépített fűtőtest teljesítményt a navigációs sávban!")
        else:
            with st.spinner("Összehasonlítás számítása..."):
                try:
                    # Dinamikus fűtésvezérlő adatainak lekérése
                    smart_query = get_smart_controller_data(start_date, end_date)
                    
                    # Termosztátos vezérlő adatainak lekérése
                    thermostat_query = get_thermostat_controller_data(start_date, end_date)
                    
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
                        
                        # Mérési intervallum (15 perc = 0.25 óra)
                        time_interval_hours = 0.25
                        
                        # Napi energia számítás: teljesítmény (kW) × idő (h) = energia (kWh)
                        # A value oszlop kW-ban van, szorozni kell az időintervallummal
                        smart_df['energy_kwh'] = smart_df['value'] * time_interval_hours
                        thermostat_df['energy_kwh'] = thermostat_df['value'] * time_interval_hours
                        
                        smart_daily_energy_df = smart_df.groupby('date')['energy_kwh'].sum().reset_index()
                        smart_daily_energy_df.columns = ['date', 'daily_energy_kwh']
                        thermostat_daily_energy_df = thermostat_df.groupby('date')['energy_kwh'].sum().reset_index()
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
                        # smart_daily_energy és thermostat_daily_energy kWh-ban van
                        # Működési órák h-ban van
                        # Átlagos teljesítmény = energia / idő = kWh / h = kW, majd W-ba konvertálás
                        if smart_operating_hours > 0:
                            smart_avg = (smart_daily_energy / smart_operating_hours) * 1000  # kW -> W konverzió
                        else:
                            smart_avg = 0
                        
                        if thermostat_operating_hours > 0:
                            thermostat_avg = (thermostat_daily_energy / thermostat_operating_hours) * 1000  # kW -> W konverzió
                        else:
                            thermostat_avg = 0
                        
                        # Beépített fűtőtest: egyszerű számítás
                        heater_usage_hours = 24  # óra
                        heater_daily_energy = (heater_power * heater_usage_hours) / 1000.0  # kWh
                        # Beépített fűtőtest konstans teljesítménye (W)
                        heater_avg = heater_power
                        
                        # Veszteségi energiaár költségek számítása dátum alapján
                        # Költség = Napi energia (kWh) × Veszteségi ár (Ft/kWh)
                        # 2024-es adatokhoz 2024-es ár, 2025-ös adatokhoz 2025-ös ár
                        if loss_price_2024 is not None and loss_price_2025 is not None:
                            # Dátum alapján választjuk ki a megfelelő árat minden napra
                            smart_daily_energy_df['year'] = pd.to_datetime(smart_daily_energy_df['date']).dt.year
                            thermostat_daily_energy_df['year'] = pd.to_datetime(thermostat_daily_energy_df['date']).dt.year
                            
                            # Napi költségek számítása dátum alapján
                            smart_daily_energy_df['daily_cost_ft'] = smart_daily_energy_df.apply(
                                lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            thermostat_daily_energy_df['daily_cost_ft'] = thermostat_daily_energy_df.apply(
                                lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            # Átlagos napi költségek számítása
                            smart_loss_cost = smart_daily_energy_df['daily_cost_ft'].mean()  # Ft/nap
                            thermostat_loss_cost = thermostat_daily_energy_df['daily_cost_ft'].mean()  # Ft/nap
                            
                            # Beépített fűtőtest költsége - dátum alapján
                            # Számoljuk meg, hogy hány nap 2024-es és hány nap 2025-ös
                            days_2024_total = (smart_daily_energy_df['year'] == 2024).sum()
                            days_2025_total = (smart_daily_energy_df['year'] == 2025).sum()
                            total_days = len(smart_daily_energy_df)
                            
                            if total_days > 0:
                                # Súlyozott átlagos ár a beépített fűtőtesthez
                                avg_price_heater = (days_2024_total * loss_price_2024 + days_2025_total * loss_price_2025) / total_days
                            else:
                                avg_price_heater = loss_price_2025
                            
                            heater_loss_cost = heater_daily_energy * avg_price_heater  # Ft/nap
                            
                            # Megtakarítás számítása veszteségi energiaár alapján
                            # Megtakarítás = (Beépített napi energia - Dinamikus fűtésvezérlő napi energia) × Veszteségi ár
                            smart_savings_energy = heater_daily_energy - smart_daily_energy  # kWh/nap
                            thermostat_savings_energy = heater_daily_energy - thermostat_daily_energy  # kWh/nap
                            
                            # Megtakarítás költség számítása dátum alapján
                            # Minden napra külön számoljuk a megtakarítást a megfelelő árral
                            smart_daily_energy_df['daily_savings_energy'] = heater_daily_energy - smart_daily_energy_df['daily_energy_kwh']
                            smart_daily_energy_df['daily_savings_cost'] = smart_daily_energy_df.apply(
                                lambda row: row['daily_savings_energy'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            thermostat_daily_energy_df['daily_savings_energy'] = heater_daily_energy - thermostat_daily_energy_df['daily_energy_kwh']
                            thermostat_daily_energy_df['daily_savings_cost'] = thermostat_daily_energy_df.apply(
                                lambda row: row['daily_savings_energy'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            # Átlagos napi megtakarítás költség
                            smart_savings_cost = smart_daily_energy_df['daily_savings_cost'].mean()  # Ft/nap
                            thermostat_savings_cost = thermostat_daily_energy_df['daily_savings_cost'].mean()  # Ft/nap
                            
                            # Átlagos árak számítása (kompatibilitás miatt)
                            if total_days > 0:
                                avg_price_smart = (days_2024_total * loss_price_2024 + days_2025_total * loss_price_2025) / total_days
                                avg_price_thermo = avg_price_smart  # Ugyanaz az időszak
                            else:
                                avg_price_smart = loss_price_2025
                                avg_price_thermo = loss_price_2025
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
                            # Számított értékek - Dinamikus fűtésvezérlő vs Beépített fűtőtest
                            # Energia különbség kWh-ban
                            consumption_diff_smart_heater = smart_daily_energy - heater_daily_energy
                            # Megtakarítás pozitív értékben (ha negatív, akkor nincs megtakarítás)
                            cost_diff_smart_heater = -smart_savings_cost  # Negatív, mert megtakarítás
                            monthly_savings_smart = smart_savings_cost * 30
                            yearly_savings_smart = smart_savings_cost * 365
                            
                            # Számított értékek - Termosztátos vezérlő vs Beépített fűtőtest
                            # Energia különbség kWh-ban
                            consumption_diff_thermo_heater = thermostat_daily_energy - heater_daily_energy
                            # Megtakarítás pozitív értékben (ha negatív, akkor nincs megtakarítás)
                            cost_diff_thermo_heater = -thermostat_savings_cost  # Negatív, mert megtakarítás
                            monthly_savings_thermo = thermostat_savings_cost * 30
                            yearly_savings_thermo = thermostat_savings_cost * 365
                            
                            monthly_diff_smart_heater = cost_diff_smart_heater * 30
                            yearly_diff_smart_heater = cost_diff_smart_heater * 365
                            monthly_diff_thermo_heater = cost_diff_thermo_heater * 30
                            yearly_diff_thermo_heater = cost_diff_thermo_heater * 365
                            
                            # Összehasonlítás táblázatos megjelenítése
                            st.write("### Összehasonlítás eredmények")
                            
                            # Fogyasztás összehasonlítás táblázat - kWh-ban
                            consumption_data = {
                                'Vezérlő típus': ['Dinamikus fűtésvezérlő', 'Termosztátos vezérlő', 'Beépített fűtőtest'],
                                'Napi energia fogyasztás (kWh)': [
                                    f"{smart_daily_energy:.2f}",
                                    f"{thermostat_daily_energy:.2f}",
                                    f"{heater_daily_energy:.2f}"
                                ]
                            }
                            
                            consumption_df = pd.DataFrame(consumption_data)
                            st.dataframe(
                                consumption_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Vezérlő típus": st.column_config.TextColumn("Vezérlő típus", width="medium"),
                                    "Napi energia fogyasztás (kWh)": st.column_config.TextColumn("Napi energia fogyasztás (kWh)", width="large")
                                }
                            )
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Költség összehasonlítás táblázat
                            st.write("### Költség összehasonlítás")
                            
                            cost_data = {
                                'Vezérlő típus': ['Dinamikus fűtésvezérlő', 'Termosztátos vezérlő', 'Beépített fűtőtest'],
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
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Veszteségi energiaár megtakarítás táblázat
                            st.write("## Veszteségi energiaár megtakarítás")
                            
                            # Dinamikus fűtésvezérlő megtakarítás
                            if smart_savings_cost > 0:
                                st.write("#### Dinamikus fűtésvezérlő vs Beépített fűtőtest")
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
                                st.info("Az okosvezérlő nem takarít meg energiát a hagyományos fűtőtesthez képest.")
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Termosztátos vezérlő megtakarítás
                            if thermostat_savings_cost > 0:
                                st.write("#### Termosztátos vezérlő vs Beépített fűtőtest")
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
                                st.info("A termosztátos vezérlő nem takarít meg energiát a hagyományos fűtőtesthez képest.")
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Fogyasztási megtakarítás számítás
                            st.write("## Fogyasztási megtakarítás")
                            
                            # Dinamikus fűtésvezérlő vs Beépített fűtőtest
                            if consumption_diff_smart_heater < 0:
                                # Napi energia megtakarítás kWh-ban
                                savings_kwh_day = abs(consumption_diff_smart_heater)
                                # Havi energia megtakarítás kWh-ban
                                savings_kwh_month = savings_kwh_day * 30
                                # Éves energia megtakarítás kWh-ban
                                savings_kwh_year = savings_kwh_day * 365
                                
                                st.write("#### Dinamikus fűtésvezérlő vs Beépített fűtőtest")
                                
                                savings_data_smart_heater = {
                                    'Időszak': ['Napi', 'Havi', 'Éves'],
                                    'Energia megtakarítás (kWh)': [
                                        f"{savings_kwh_day:.2f}",
                                        f"{savings_kwh_month:.2f}",
                                        f"{savings_kwh_year:.2f}"
                                    ]
                                }
                                savings_df_smart_heater = pd.DataFrame(savings_data_smart_heater)
                                st.dataframe(
                                    savings_df_smart_heater,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                        "Energia megtakarítás (kWh)": st.column_config.TextColumn("Energia megtakarítás (kWh)", width="medium")
                                    }
                                )
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Termosztátos vezérlő vs Beépített fűtőtest
                            if consumption_diff_thermo_heater < 0:
                                # Napi energia megtakarítás kWh-ban
                                savings_kwh_day = abs(consumption_diff_thermo_heater)
                                # Havi energia megtakarítás kWh-ban
                                savings_kwh_month = savings_kwh_day * 30
                                # Éves energia megtakarítás kWh-ban
                                savings_kwh_year = savings_kwh_day * 365
                                
                                st.write("#### Termosztátos vezérlő vs Beépített fűtőtest")
                                
                                savings_data_thermo_heater = {
                                    'Időszak': ['Napi', 'Havi', 'Éves'],
                                    'Energia megtakarítás (kWh)': [
                                        f"{savings_kwh_day:.2f}",
                                        f"{savings_kwh_month:.2f}",
                                        f"{savings_kwh_year:.2f}"
                                    ]
                                }
                                savings_df_thermo_heater = pd.DataFrame(savings_data_thermo_heater)
                                st.dataframe(
                                    savings_df_thermo_heater,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                        "Energia megtakarítás (kWh)": st.column_config.TextColumn("Energia megtakarítás (kWh)", width="medium")
                                    }
                                )
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Költség különbség táblázat
                            st.write("## Költség különbség")
                            
                            # Dinamikus fűtésvezérlő vs Beépített fűtőtest
                            st.write("#### Dinamikus fűtésvezérlő vs Beépített fűtőtest")
                            
                            cost_diff_data_smart_heater = {
                                'Időszak': ['Napi', 'Havi', 'Éves'],
                                'Különbség (Ft)': [
                                    f"{cost_diff_smart_heater:.2f}",
                                    f"{monthly_diff_smart_heater:.2f}",
                                    f"{yearly_diff_smart_heater:.2f}"
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
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Termosztátos vezérlő vs Beépített fűtőtest
                            st.write("#### Termosztátos vezérlő vs Beépített fűtőtest")
                            
                            cost_diff_data_thermo_heater = {
                                'Időszak': ['Napi', 'Havi', 'Éves'],
                                'Különbség (Ft)': [
                                    f"{cost_diff_thermo_heater:.2f}",
                                    f"{monthly_diff_thermo_heater:.2f}",
                                    f"{yearly_diff_thermo_heater:.2f}"
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
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Összefoglaló táblázat
                            st.write("### Összefoglaló")
                            
                            summary_data = {
                                'Összehasonlítás': [
                                    'Dinamikus fűtésvezérlő vs Beépített fűtőtest',
                                    'Termosztátos vezérlő vs Beépített fűtőtest'
                                ],
                                'Energia különbség (kWh)': [
                                    f"{consumption_diff_smart_heater:.2f}",
                                    f"{consumption_diff_thermo_heater:.2f}"
                                ],
                                'Napi költség különbség (Ft)': [
                                    f"{cost_diff_smart_heater:.2f}",
                                    f"{cost_diff_thermo_heater:.2f}"
                                ],
                                'Havi költség különbség (Ft)': [
                                    f"{monthly_diff_smart_heater:.2f}",
                                    f"{monthly_diff_thermo_heater:.2f}"
                                ],
                                'Éves költség különbség (Ft)': [
                                    f"{yearly_diff_smart_heater:.2f}",
                                    f"{yearly_diff_thermo_heater:.2f}"
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
                            
                            
                            smart_daily_operating_hours = smart_df.groupby('date').apply(
                                lambda x: (x['value'] > 0).sum() * time_interval_hours
                            )
                            thermostat_daily_operating_hours = thermostat_df.groupby('date').apply(
                                lambda x: (x['value'] > 0).sum() * time_interval_hours
                            )
                            
                            # Napi energia és teljesítmény számítása
                            # Napi energia kWh-ban (már kiszámítva az energy_kwh oszlopból)
                            smart_daily_energy_per_day = smart_df.groupby('date')['energy_kwh'].sum()
                            thermostat_daily_energy_per_day = thermostat_df.groupby('date')['energy_kwh'].sum()
                            
                            # Átlagos teljesítmény W-ban = (Energia kWh / Működési óra) * 1000
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
                                # Napi költségek már számolva vannak dátum alapján feljebb
                                # Ha még nincs 'daily_cost_ft' oszlop, akkor számoljuk dátum alapján
                                if 'daily_cost_ft' not in smart_daily_energy_df.columns:
                                    if 'year' not in smart_daily_energy_df.columns:
                                        smart_daily_energy_df['year'] = pd.to_datetime(smart_daily_energy_df['date']).dt.year
                                    smart_daily_energy_df['daily_cost_ft'] = smart_daily_energy_df.apply(
                                        lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                        axis=1
                                    )
                                
                                if 'daily_cost_ft' not in thermostat_daily_energy_df.columns:
                                    if 'year' not in thermostat_daily_energy_df.columns:
                                        thermostat_daily_energy_df['year'] = pd.to_datetime(thermostat_daily_energy_df['date']).dt.year
                                    thermostat_daily_energy_df['daily_cost_ft'] = thermostat_daily_energy_df.apply(
                                        lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                        axis=1
                                    )
                                
                                # Beépített fűtőtest konstans költsége - dátum alapján súlyozott átlag
                                # Számoljuk újra az átlagos árat
                                if 'year' in smart_daily_energy_df.columns:
                                    days_2024_total = (smart_daily_energy_df['year'] == 2024).sum()
                                    days_2025_total = (smart_daily_energy_df['year'] == 2025).sum()
                                    total_days = len(smart_daily_energy_df)
                                    
                                    if total_days > 0:
                                        avg_price_heater = (days_2024_total * loss_price_2024 + days_2025_total * loss_price_2025) / total_days
                                    else:
                                        avg_price_heater = loss_price_2025
                                else:
                                    avg_price_heater = loss_price_2025
                                
                                heater_daily_cost_constant = heater_daily_energy * avg_price_heater
                                
                                st.write("## Fogyasztás-költség korreláció")
                                
                                # Fogyasztás W-ban és költség Ft-ban összekapcsolása
                                # Dinamikus fűtésvezérlő adatok - összekapcsoljuk a helyes teljesítmény értékeket a költségekkel
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
                                    # 1. Dinamikus fűtésvezérlő vs Beépített fűtőtest diagram
                                    st.write("#### Dinamikus fűtésvezérlő vs Beépített fűtőtest")
                                    fig_scatter_smart = go.Figure()
                                    
                                    # Dinamikus fűtésvezérlő pontok
                                    fig_scatter_smart.add_trace(go.Scatter(
                                        x=smart_consumption_cost_df['fogyasztas_w'],
                                        y=smart_consumption_cost_df['koltseg_ft'],
                                        mode='markers',
                                        name='Dinamikus fűtésvezérlő',
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
                                    
                                    # Beépített fűtőtest referencia pont
                                    fig_scatter_smart.add_trace(go.Scatter(
                                        x=[heater_avg],
                                        y=[heater_daily_cost_constant],
                                        mode='markers',
                                        name='Beépített fűtőtest',
                                        marker=dict(
                                            color='gray',
                                            size=15,
                                            symbol='diamond',
                                            line=dict(width=2, color='black')
                                        ),
                                        text=f"Beépített fűtőtest<br>Fogyasztás: {heater_avg:.2f} W<br>Költség: {heater_daily_cost_constant:.2f} Ft",
                                        hoverinfo='text'
                                    ))
                                    
                                    # Dinamikus fűtésvezérlő trendvonal
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
                                            name='Dinamikus fűtésvezérlő trendvonal',
                                            line=dict(color='white', width=4, dash='dot'),
                                            showlegend=True
                                        ))
                                    
                                    fig_scatter_smart.update_layout(
                                        xaxis_title="Fogyasztás (W)",
                                        yaxis_title="Költség (Ft)",
                                        hovermode='closest',
                                        template="plotly_white",
                                        height=500,
                                        title="Dinamikus fűtésvezérlő vs Beépített fűtőtest",
                                        legend=dict(
                                            yanchor="top",
                                            y=0.99,
                                            xanchor="left",
                                            x=0.01
                                        )
                                    )
                                    
                                    st.plotly_chart(fig_scatter_smart, use_container_width=True)
                                
                                with col2:
                                    # 2. Termosztátos vezérlő vs Beépített fűtőtest diagram
                                    st.write("#### Termosztátos vezérlő vs Beépített fűtőtest")
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
                                    
                                    # Beépített fűtőtest referencia pont
                                    fig_scatter_thermo.add_trace(go.Scatter(
                                        x=[heater_avg],
                                        y=[heater_daily_cost_constant],
                                        mode='markers',
                                        name='Beépített fűtőtest',
                                        marker=dict(
                                            color='gray',
                                            size=15,
                                            symbol='diamond',
                                            line=dict(width=2, color='black')
                                        ),
                                        text=f"Beépített fűtőtest<br>Fogyasztás: {heater_avg:.2f} W<br>Költség: {heater_daily_cost_constant:.2f} Ft",
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
                                        title="Termosztátos vezérlő vs Beépített fűtőtest",
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
        st.warning("Az összehasonlításhoz szükségesek az E.ON árak!")

