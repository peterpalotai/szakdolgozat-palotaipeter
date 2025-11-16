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
                            
                            # Napi költségek számítása dátum alapján - minden napra külön
                            smart_daily_energy_df['daily_cost_ft'] = smart_daily_energy_df.apply(
                                lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            thermostat_daily_energy_df['daily_cost_ft'] = thermostat_daily_energy_df.apply(
                                lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            # Számoljuk meg, hogy hány nap 2024-es és hány nap 2025-ös
                            days_2024_total = (smart_daily_energy_df['year'] == 2024).sum()
                            days_2025_total = (smart_daily_energy_df['year'] == 2025).sum()
                            total_days = len(smart_daily_energy_df)
                            
                            # Beépített fűtőtest költsége - minden napra külön számolva dátum alapján
                            smart_daily_energy_df['heater_daily_cost_ft'] = smart_daily_energy_df.apply(
                                lambda row: heater_daily_energy * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            thermostat_daily_energy_df['heater_daily_cost_ft'] = thermostat_daily_energy_df.apply(
                                lambda row: heater_daily_energy * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            # Összes költségek összegzése, majd átlagos napi érték számítása
                            total_smart_cost = smart_daily_energy_df['daily_cost_ft'].sum()  # Összes Ft
                            total_thermostat_cost = thermostat_daily_energy_df['daily_cost_ft'].sum()  # Összes Ft
                            total_heater_cost = smart_daily_energy_df['heater_daily_cost_ft'].sum()  # Összes Ft
                            
                            # Átlagos napi költségek (összeg / napok száma)
                            smart_loss_cost = total_smart_cost / total_days if total_days > 0 else 0  # Ft/nap
                            thermostat_loss_cost = total_thermostat_cost / total_days if total_days > 0 else 0  # Ft/nap
                            heater_loss_cost = total_heater_cost / total_days if total_days > 0 else 0  # Ft/nap
                            
                            # Megtakarítás számítása veszteségi energiaár alapján
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
                            
                            # Összes megtakarítás összegzése, majd átlagos napi érték számítása
                            total_smart_savings_cost = smart_daily_energy_df['daily_savings_cost'].sum()  # Összes Ft
                            total_thermostat_savings_cost = thermostat_daily_energy_df['daily_savings_cost'].sum()  # Összes Ft
                            
                            # Összes megtakarítás energia összegzése
                            total_smart_savings_energy = smart_daily_energy_df['daily_savings_energy'].sum()  # Összes kWh
                            total_thermostat_savings_energy = thermostat_daily_energy_df['daily_savings_energy'].sum()  # Összes kWh
                            
                            # Dinamikus vs Termosztátos megtakarítás számítása - naponta
                            # Összevonjuk a két DataFrame-et dátum alapján
                            smart_thermo_comparison = smart_daily_energy_df[['date', 'daily_energy_kwh', 'daily_cost_ft', 'year']].copy()
                            smart_thermo_comparison.columns = ['date', 'smart_energy', 'smart_cost', 'year']
                            thermo_comparison = thermostat_daily_energy_df[['date', 'daily_energy_kwh', 'daily_cost_ft']].copy()
                            thermo_comparison.columns = ['date', 'thermo_energy', 'thermo_cost']
                            smart_thermo_comparison = smart_thermo_comparison.merge(thermo_comparison, on='date', how='inner')
                            
                            # Megtakarítás számítása: termosztátos - dinamikus (ha negatív, akkor dinamikus takarít meg)
                            smart_thermo_comparison['daily_savings_energy_smart_vs_thermo'] = smart_thermo_comparison['thermo_energy'] - smart_thermo_comparison['smart_energy']
                            smart_thermo_comparison['daily_savings_cost_smart_vs_thermo'] = smart_thermo_comparison.apply(
                                lambda row: row['daily_savings_energy_smart_vs_thermo'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
                                axis=1
                            )
                            
                            # Összes megtakarítás dinamikus vs termosztátos
                            total_smart_vs_thermo_savings_energy = smart_thermo_comparison['daily_savings_energy_smart_vs_thermo'].sum()  # Összes kWh
                            total_smart_vs_thermo_savings_cost = smart_thermo_comparison['daily_savings_cost_smart_vs_thermo'].sum()  # Összes Ft
                            
                            # Átlagos napi megtakarítás (összeg / napok száma)
                            smart_savings_cost = total_smart_savings_cost / total_days if total_days > 0 else 0  # Ft/nap
                            thermostat_savings_cost = total_thermostat_savings_cost / total_days if total_days > 0 else 0  # Ft/nap
                            smart_savings_energy = total_smart_savings_energy / total_days if total_days > 0 else 0  # kWh/nap
                            thermostat_savings_energy = total_thermostat_savings_energy / total_days if total_days > 0 else 0  # kWh/nap
                            
                            # Dinamikus vs Termosztátos átlagos napi megtakarítás
                            comparison_days = len(smart_thermo_comparison)
                            smart_vs_thermo_savings_energy = total_smart_vs_thermo_savings_energy / comparison_days if comparison_days > 0 else 0  # kWh/nap
                            smart_vs_thermo_savings_cost = total_smart_vs_thermo_savings_cost / comparison_days if comparison_days > 0 else 0  # Ft/nap
                            
                            # Átlagos árak számítása (kompatibilitás miatt)
                            if total_days > 0:
                                avg_price_smart = (days_2024_total * loss_price_2024 + days_2025_total * loss_price_2025) / total_days
                                avg_price_thermo = avg_price_smart  # Ugyanaz az időszak
                                avg_price_heater = avg_price_smart
                            else:
                                avg_price_smart = loss_price_2025
                                avg_price_thermo = loss_price_2025
                                avg_price_heater = loss_price_2025
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
                            
                            # Számított értékek - Dinamikus fűtésvezérlő vs Termosztátos vezérlő (fogyasztási megtakarítás)
                            # Energia különbség kWh-ban: termosztátos - dinamikus (ha pozitív, dinamikus takarít meg)
                            consumption_diff_smart_thermo = thermostat_daily_energy - smart_daily_energy
                            # Költség különbség: negatív, mert megtakarítás
                            cost_diff_smart_thermo = -smart_vs_thermo_savings_cost
                            monthly_diff_smart_thermo = cost_diff_smart_thermo * 30
                            yearly_diff_smart_thermo = cost_diff_smart_thermo * 365
                            
                            monthly_diff_smart_heater = cost_diff_smart_heater * 30
                            yearly_diff_smart_heater = cost_diff_smart_heater * 365
                            monthly_diff_thermo_heater = cost_diff_thermo_heater * 30
                            yearly_diff_thermo_heater = cost_diff_thermo_heater * 365
                            

            
                            
                            # Legördülő lista a vezérlő kiválasztásához - bal oldali elhelyezés
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                controller_choice = st.selectbox(
                                    "Vezérlő kiválasztása:",
                                    ["Dinamikus fűtésvezérlő", "Termosztátos vezérlő"],
                                    key="controller_comparison_choice"
                                )
                            
                            # Kiválasztott vezérlő adatainak előkészítése
                            if controller_choice == "Dinamikus fűtésvezérlő":
                                selected_df = smart_daily_energy_df[['date', 'daily_energy_kwh', 'daily_cost_ft']].copy()
                                controller_name = "Dinamikus fűtésvezérlő"
                            else:
                                selected_df = thermostat_daily_energy_df[['date', 'daily_energy_kwh', 'daily_cost_ft']].copy()
                                controller_name = "Termosztátos vezérlő"
                            
                            # Dátum formázása és oszlopok átnevezése
                            selected_df['date'] = pd.to_datetime(selected_df['date']).dt.strftime('%Y-%m-%d')
                            selected_df = selected_df.sort_values('date')
                            selected_df.columns = ['Dátum', 'Fogyasztás (kWh)', 'Költség (Ft)']
                            
                            # Táblázat megjelenítése
                            st.dataframe(
                                selected_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Dátum": st.column_config.TextColumn("Dátum", width="medium"),
                                    "Fogyasztás (kWh)": st.column_config.NumberColumn("Fogyasztás (kWh)", format="%.2f", width="medium"),
                                    "Költség (Ft)": st.column_config.NumberColumn("Költség (Ft)", format="%.2f", width="medium")
                                }
                            )
                            
                            # Beépített fűtőtest adatok megjelenítése a táblázat alatt
                            st.write("")
                            st.write("**Beépített fűtőtest:**")
                            
                            # 2024-es és 2025-ös napi költségek számítása
                            if 'year' in smart_daily_energy_df.columns:
                                heater_cost_2024 = smart_daily_energy_df[smart_daily_energy_df['year'] == 2024]['heater_daily_cost_ft'].mean() if (smart_daily_energy_df['year'] == 2024).any() else None
                                heater_cost_2025 = smart_daily_energy_df[smart_daily_energy_df['year'] == 2025]['heater_daily_cost_ft'].mean() if (smart_daily_energy_df['year'] == 2025).any() else None
                            else:
                                heater_cost_2024 = None
                                heater_cost_2025 = None
                            
                            # Ha nincs év oszlop, akkor számoljuk dátum alapján
                            if heater_cost_2024 is None or heater_cost_2025 is None:
                                smart_daily_energy_df['year'] = pd.to_datetime(smart_daily_energy_df['date']).dt.year
                                heater_cost_2024 = smart_daily_energy_df[smart_daily_energy_df['year'] == 2024]['heater_daily_cost_ft'].mean() if (smart_daily_energy_df['year'] == 2024).any() else None
                                heater_cost_2025 = smart_daily_energy_df[smart_daily_energy_df['year'] == 2025]['heater_daily_cost_ft'].mean() if (smart_daily_energy_df['year'] == 2025).any() else None
                            
                            # Ha még mindig nincs érték, akkor számoljuk az ár alapján
                            if heater_cost_2024 is None and loss_price_2024 is not None:
                                heater_cost_2024 = heater_daily_energy * loss_price_2024
                            if heater_cost_2025 is None and loss_price_2025 is not None:
                                heater_cost_2025 = heater_daily_energy * loss_price_2025
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Napi fogyasztás (kWh)", f"{heater_daily_energy:.2f}")
                            with col2:
                                if heater_cost_2024 is not None:
                                    st.metric("2024 - Napi veszteségi energiaár költség (Ft)", f"{heater_cost_2024:.2f}")
                                else:
                                    st.metric("2024 - Napi veszteségi energiaár költség (Ft)", "N/A")
                            with col3:
                                if heater_cost_2025 is not None:
                                    st.metric("2025 - Napi veszteségi energiaár költség (Ft)", f"{heater_cost_2025:.2f}")
                                else:
                                    st.metric("2025 - Napi veszteségi energiaár költség (Ft)", "N/A")
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Összehasonlítás táblázat
                            st.write("## Összehasonlítás")
                            
                            # Checkbox-ok az összehasonlítás kiválasztásához
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                st.write("**Vezérlők kiválasztása:**")
                                
                                # Először olvassuk be a jelenlegi értékeket (ha vannak session state-ben)
                                current_smart = st.session_state.get("savings_smart_checkbox", False)
                                current_thermo = st.session_state.get("savings_thermo_checkbox", False)
                                current_heater = st.session_state.get("savings_heater_checkbox", False)
                                
                                # Számoljuk meg, hány van kiválasztva
                                current_count = sum([current_smart, current_thermo, current_heater])
                                
                                # Ha 2 van kiválasztva, tiltsuk le a harmadikat
                                smart_selected = st.checkbox(
                                    "Dinamikus fűtésvezérlő", 
                                    key="savings_smart_checkbox",
                                    disabled=(current_count == 2 and not current_smart)
                                )
                                
                                # Újraszámoljuk a kiválasztottak számát (a smart checkbox már frissült)
                                current_count_after_smart = sum([
                                    st.session_state.get("savings_smart_checkbox", False),
                                    current_thermo,
                                    current_heater
                                ])
                                
                                thermo_selected = st.checkbox(
                                    "Termosztátos vezérlő", 
                                    key="savings_thermo_checkbox",
                                    disabled=(current_count_after_smart == 2 and not current_thermo)
                                )
                                
                                # Újraszámoljuk a kiválasztottak számát (a thermo checkbox már frissült)
                                current_count_after_thermo = sum([
                                    st.session_state.get("savings_smart_checkbox", False),
                                    st.session_state.get("savings_thermo_checkbox", False),
                                    current_heater
                                ])
                                
                                heater_selected = st.checkbox(
                                    "Beépített fűtőtest", 
                                    key="savings_heater_checkbox",
                                    disabled=(current_count_after_thermo == 2 and not current_heater)
                                )
                            
                            # Ellenőrizzük, hogy pontosan 2 van-e kiválasztva
                            selected_count = sum([smart_selected, thermo_selected, heater_selected])
                            
                            # Kiválasztott összehasonlítás megjelenítése - két oszlopban
                            if selected_count == 2:
                                # Meghatározzuk a címeket és adatokat
                                if smart_selected and thermo_selected:
                                    # Dinamikus vs Termosztátos
                                    comparison_title = "Dinamikus fűtésvezérlő vs Termosztátos vezérlő"
                                    # Energiaár megtakarítás
                                    if smart_vs_thermo_savings_cost > 0:
                                        energy_savings_energy = smart_vs_thermo_savings_energy
                                        energy_savings_cost = smart_vs_thermo_savings_cost
                                        note_text = None
                                    elif smart_vs_thermo_savings_cost < 0:
                                        energy_savings_energy = abs(smart_vs_thermo_savings_energy)
                                        energy_savings_cost = abs(smart_vs_thermo_savings_cost)
                                        note_text = "*Megjegyzés: A termosztátos vezérlő takarít meg a dinamikus vezérlőhöz képest.*"
                                    else:
                                        energy_savings_energy = 0
                                        energy_savings_cost = 0
                                        note_text = None
                                    # Fogyasztás megtakarítás
                                    if consumption_diff_smart_thermo < 0:
                                        consumption_savings = abs(consumption_diff_smart_thermo)
                                    else:
                                        consumption_savings = 0
                                
                                elif smart_selected and heater_selected:
                                    # Dinamikus vs Beépített
                                    comparison_title = "Dinamikus fűtésvezérlő vs Beépített fűtőtest"
                                    energy_savings_energy = smart_savings_energy
                                    energy_savings_cost = smart_savings_cost
                                    note_text = None
                                    if consumption_diff_smart_heater < 0:
                                        consumption_savings = abs(consumption_diff_smart_heater)
                                    else:
                                        consumption_savings = 0
                                
                                elif thermo_selected and heater_selected:
                                    # Termosztátos vs Beépített
                                    comparison_title = "Termosztátos vezérlő vs Beépített fűtőtest"
                                    energy_savings_energy = thermostat_savings_energy
                                    energy_savings_cost = thermostat_savings_cost
                                    note_text = None
                                    if consumption_diff_thermo_heater < 0:
                                        consumption_savings = abs(consumption_diff_thermo_heater)
                                    else:
                                        consumption_savings = 0
                                
                                # Cím megjelenítése
                                st.write(f"#### {comparison_title}")
                                if note_text:
                                    st.write(note_text)
                                
                                # Energiaár megtakarítás táblázat megjelenítése
                                st.write("##### Energiaár megtakarítás")
                                if energy_savings_cost > 0 or (energy_savings_cost == 0 and energy_savings_energy == 0):
                                    energy_savings_data = {
                                        'Időszak': ['Napi', 'Havi', 'Éves'],
                                        'Fogyasztás megtakarítás (kWh)': [
                                            f"{energy_savings_energy:.2f}",
                                            f"{energy_savings_energy * 30:.2f}",
                                            f"{energy_savings_energy * 365:.2f}"
                                        ],
                                        'Pénzügyi megtakarítás (Ft)': [
                                            f"{energy_savings_cost:.2f}",
                                            f"{energy_savings_cost * 30:.2f}",
                                            f"{energy_savings_cost * 365:.2f}"
                                        ]
                                    }
                                    energy_savings_df = pd.DataFrame(energy_savings_data)
                                    st.dataframe(
                                        energy_savings_df,
                                        use_container_width=True,
                                        hide_index=True,
                                        column_config={
                                            "Időszak": st.column_config.TextColumn("Időszak", width="medium"),
                                            "Fogyasztás megtakarítás (kWh)": st.column_config.TextColumn("Fogyasztás megtakarítás (kWh)", width="medium"),
                                            "Pénzügyi megtakarítás (Ft)": st.column_config.TextColumn("Pénzügyi megtakarítás (Ft)", width="medium")
                                        }
                                    )
                                else:
                                    st.info("Nincs energiaár megtakarítás.")
                            
                            elif selected_count != 2:
                                st.info("Kérjük, válasszon ki 2 vezérlőt az összehasonlításhoz!")
                            
                            st.write("---")  # Elválasztó vonal a táblázatok között
                            st.write("")  # Üres sor a vonal alatt
                            
                            # Összefoglaló táblázat
                            st.write("### Összefoglaló")
                            
                            summary_data = {
                                'Összehasonlítás': [
                                    'Dinamikus fűtésvezérlő vs Beépített fűtőtest',
                                    'Termosztátos vezérlő vs Beépített fűtőtest',
                                    'Dinamikus fűtésvezérlő vs Termosztátos vezérlő'
                                ],
                                'Fogyasztás különbség (kWh)': [
                                    f"{consumption_diff_smart_heater:.2f}",
                                    f"{consumption_diff_thermo_heater:.2f}",
                                    f"{consumption_diff_smart_thermo:.2f}"
                                ],
                                'Napi költség különbség (Ft)': [
                                    f"{cost_diff_smart_heater:.2f}",
                                    f"{cost_diff_thermo_heater:.2f}",
                                    f"{cost_diff_smart_thermo:.2f}"
                                ],
                                'Havi költség különbség (Ft)': [
                                    f"{monthly_diff_smart_heater:.2f}",
                                    f"{monthly_diff_thermo_heater:.2f}",
                                    f"{monthly_diff_smart_thermo:.2f}"
                                ],
                                'Éves költség különbség (Ft)': [
                                    f"{yearly_diff_smart_heater:.2f}",
                                    f"{yearly_diff_thermo_heater:.2f}",
                                    f"{yearly_diff_smart_thermo:.2f}"
                                ]
                            }
                            
                            summary_df = pd.DataFrame(summary_data)
                            st.dataframe(
                                summary_df,
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            investment_cost = st.session_state.get('investment_cost', 0.0)
                            
                            if investment_cost > 0 and smart_savings_cost > 0:
                                # Megtérülési idő számítása napokban
                                payback_days = investment_cost / smart_savings_cost
                                payback_months = payback_days / 30
                                payback_years = payback_days / 365
                                
                                # Megtérülési dátum számítása
                                from datetime import datetime, timedelta
                                payback_date = datetime.now() + timedelta(days=int(payback_days))
                                
                                # Metrikák megjelenítése
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Megtérülési idő (nap)", f"{payback_days:.1f}")
                                with col2:
                                    st.metric("Megtérülési idő (hónap)", f"{payback_months:.1f}")
                                with col3:
                                    st.metric("Megtérülési idő (év)", f"{payback_years:.2f}")
                                
                                st.write(f"**Becsült megtérülési dátum:** {payback_date.strftime('%Y-%m-%d')}")
                                
                                # Vonaldiagram: kumulatív megtakarítás vs beruházás
                                st.write("### Megtérülési görbe")
                                
                                # Adatok előkészítése a diagramhoz (max 5 év vagy amíg megtérül)
                                max_days = min(int(payback_days * 1.2), 365 * 5)  # 20% túllépés vagy max 5 év
                                days_range = list(range(0, max_days + 1, 7))  # Hetente egy pont
                                
                                cumulative_savings = [smart_savings_cost * day for day in days_range]
                                investment_line = [investment_cost] * len(days_range)
                                
                                # Hónapok számítása a diagramhoz
                                months_range = [day / 30 for day in days_range]
                                
                                fig_payback = go.Figure()
                                
                                # Kumulatív megtakarítás vonal
                                fig_payback.add_trace(go.Scatter(
                                    x=months_range,
                                    y=cumulative_savings,
                                    mode='lines',
                                    name='Kumulatív megtakarítás',
                                    line=dict(color='#00CC96', width=3),
                                    hovertemplate='%{x:.1f} hónap<br>%{y:,.0f} Ft<extra></extra>'
                                ))
                                
                                # Beruházás vonal
                                fig_payback.add_trace(go.Scatter(
                                    x=months_range,
                                    y=investment_line,
                                    mode='lines',
                                    name='Beruházási költség',
                                    line=dict(color='red', width=2, dash='dash'),
                                    hovertemplate='%{x:.1f} hónap<br>%{y:,.0f} Ft<extra></extra>'
                                ))
                                
                                # Megtérülési pont jelölése
                                if payback_months <= max(days_range) / 30:
                                    fig_payback.add_trace(go.Scatter(
                                        x=[payback_months],
                                        y=[investment_cost],
                                        mode='markers',
                                        name='Megtérülési pont',
                                        marker=dict(
                                            color='green',
                                            size=15,
                                            symbol='diamond',
                                            line=dict(width=2, color='darkgreen')
                                        ),
                                        hovertemplate=f'Megtérülés: {payback_months:.1f} hónap<br>{investment_cost:,.0f} Ft<extra></extra>'
                                    ))
                                
                                fig_payback.update_layout(
                                    title="Beruházás megtérülési görbe",
                                    xaxis_title="Idő (hónap)",
                                    yaxis_title="Összeg (Ft)",
                                    hovermode='x unified',
                                    template="plotly_white",
                                    height=500,
                                    legend=dict(
                                        yanchor="top",
                                        y=0.99,
                                        xanchor="left",
                                        x=0.01
                                    )
                                )
                                
                                st.plotly_chart(fig_payback, use_container_width=True)
                                
                            elif investment_cost > 0 and smart_savings_cost <= 0:
                                st.warning("A dinamikus fűtésvezérlő jelenleg nem takarít meg pénzt a beépített fűtőtesthez képest, így a beruházás nem térül meg.")
                            elif investment_cost == 0:
                                st.info("Kérjük, adjon meg egy beruházási költséget a sidebar-ban a megtérülési számítás megjelenítéséhez.")
                            
                        else:
                            st.error("Nem sikerült kiszámítani a költségeket.")
                    
                    else:
                        st.warning("Nincs elegendő adat az összehasonlításhoz!")
                        
                except Exception as e:
                    st.error(f"Hiba az összehasonlítás során: {e}")
    else:
        st.warning("Az összehasonlításhoz szükségesek az E.ON árak!")

