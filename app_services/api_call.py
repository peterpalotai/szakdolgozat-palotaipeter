import pandas as pd
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from app_services.database import execute_query
import streamlit as st


def fetch_co2_emission_data(days_to_show=10, api_key=None):
    """
    Lekéri a CO2 kibocsátási adatokat az Electricity Maps API-ból
    és kombinálja az energiadataival az adatbázisból.
    
    Args:
        days_to_show: Hány napra visszamenőleg kérdezze le (default: 10)
        api_key: API kulcs (ha nincs megadva, session state-ből veszi)
    
    Returns:
        tuple: (co2_hourly_df, co2_hourly_with_power, daily_co2_df)
    """
    
    if api_key is None:
        return None, None, None
    
    # Dátumok számítása - először lekérdezzük az utolsó adatbázis napját
    try:
        last_date_query = "SELECT MAX(date) as last_date FROM dfv_smart_db"
        last_date_result = execute_query(last_date_query)
        if last_date_result and len(last_date_result) > 0 and last_date_result[0][0]:
            end_date = datetime.combine(last_date_result[0][0], datetime.max.time())
        else:
            end_date = datetime.now()
    except:
        end_date = datetime.now()
    
    start_date = end_date - timedelta(days=days_to_show)
    
    # API URL
    base_url = "https://api.electricitymaps.com/v3/carbon-intensity-fossil-only/past-range"
    start_str = f"{start_date.strftime('%Y-%m-%d')} {start_date.strftime('%H:%M')}"
    end_str = f"{end_date.strftime('%Y-%m-%d')} {end_date.strftime('%H:%M')}"
    
    # Órás CO2 kibocsátás API lekérdezés
    api_url = f"{base_url}?zone=HU&start={quote(start_str)}&end={quote(end_str)}&temporalGranularity=hourly"
    
    try:
        response = requests.get(
            api_url,
            headers={"auth-token": api_key}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if 'data' in data and len(data['data']) > 0:
                co2_hourly_data = []
                for item in data['data']:
                    timestamp = datetime.fromisoformat(item['datetime'].replace('Z', '+00:00'))
                    co2_intensity = item.get('value', 0)
                    co2_hourly_data.append({
                        'Dátum és idő': timestamp,
                        'CO2 Kibocsátás (g CO2/kWh)': co2_intensity,
                        'Dátum': timestamp.date()
                    })
                
                co2_hourly_df = pd.DataFrame(co2_hourly_data)
                
                # Adatbázisból energiafogyasztás lekérdezése
                try:
                    # Teljesítmény = Feszültség × Áramerősség - napi összesítés
                    energy_query = f"""
                    SELECT date, SUM(trend_smart_ul1n::numeric * trend_smart_i1::numeric)::float as daily_energy_W
                    FROM dfv_smart_db
                    WHERE date >= '{start_date.date()}' AND date <= '{end_date.date()}'
                    AND trend_smart_ul1n IS NOT NULL AND trend_smart_i1 IS NOT NULL
                    GROUP BY date
                    ORDER BY date
                    """
                    energy_data = execute_query(energy_query)
                    
                    if energy_data:
                        energy_df = pd.DataFrame(energy_data, columns=['Dátum', 'Energia (W)'])
                        energy_df['Dátum'] = pd.to_datetime(energy_df['Dátum']).dt.date
                        
                        # Konvertálás W-ból kWh-ba (15 perces mérések)
                        energy_df['Napi energia (kWh)'] = energy_df['Energia (W)'] * 0.25 / 1000
                        
                        # Napi átlagos CO2 intensity számítása
                        co2_daily_intensity = co2_hourly_df.groupby('Dátum')['CO2 Kibocsátás (g CO2/kWh)'].mean().reset_index()
                        co2_daily_intensity.columns = ['Dátum', 'Átlag CO2 (g CO2/kWh)']
                        
                        # Kombinálás az energiaadatokkal
                        daily_co2_df = pd.merge(energy_df, co2_daily_intensity, on='Dátum', how='inner')
                        
                        # Napi CO2 kibocsátás számítása
                        daily_co2_df['Napi CO2 (g)'] = daily_co2_df['Napi energia (kWh)'] * daily_co2_df['Átlag CO2 (g CO2/kWh)']
                        daily_co2_df['Napi CO2 (kg)'] = daily_co2_df['Napi CO2 (g)'] / 1000
                        
                        # Az óras adatokhoz hozzáadjuk a napi energia arányokat
                        co2_hourly_with_power = co2_hourly_df.copy()
                        co2_hourly_with_power['Dátum'] = co2_hourly_with_power['Dátum és idő'].dt.date
                        co2_hourly_with_power = pd.merge(co2_hourly_with_power, daily_co2_df[['Dátum', 'Napi energia (kWh)']], on='Dátum', how='left')
                        
                        # Órás energia számítása (egyenletes elosztás napra)
                        daily_hours = co2_hourly_with_power.groupby('Dátum').size()
                        co2_hourly_with_power['Óras energia (kWh)'] = co2_hourly_with_power.apply(
                            lambda row: row['Napi energia (kWh)'] / daily_hours[row['Dátum']] if pd.notna(row['Napi energia (kWh)']) else 0, 
                            axis=1
                        )
                        
                        # Órás CO2 kibocsátás számítása
                        co2_hourly_with_power['Óras CO2 (kg)'] = (co2_hourly_with_power['Óras energia (kWh)'] * co2_hourly_with_power['CO2 Kibocsátás (g CO2/kWh)']) / 1000
                        
                        # Konvertálás datetime-re a megjelenítéshez
                        daily_co2_df['Dátum_datetime'] = pd.to_datetime(daily_co2_df['Dátum'])
                        
                        return co2_hourly_df, co2_hourly_with_power, daily_co2_df
                    else:
                        # Ha nincs energiaadat, akkor csak CO2 intenzitást ad vissza
                        return co2_hourly_df, None, None
                        
                except Exception as e:
                    st.error(f"Hiba az energiaadatok lekérdezésekor: {e}")
                    return co2_hourly_df, None, None
            else:
                st.warning("Nincs adat a kiválasztott időszakban.")
                return None, None, None
        else:
            st.error(f"API hiba: {response.status_code} - {response.text}")
            return None, None, None
            
    except Exception as e:
        st.error(f"Hiba történt az adatok lekérése során: {e}")
        return None, None, None

