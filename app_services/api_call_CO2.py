import pandas as pd
import requests
from datetime import datetime, timedelta
from urllib.parse import quote
from app_services.database import execute_query
import streamlit as st


def fetch_co2_emission_data(days_to_show=10, api_key=None, table_name="dfv_smart_db"):
    """
    Lekéri a CO2 kibocsátási adatokat az Electricity Maps API-ból
    és kombinálja az energiadataival az adatbázisból.
    
    Args:
        days_to_show: Hány napra visszamenőleg kérdezze le (default: 10)
        api_key: API kulcs (ha nincs megadva, session state-ből veszi)
        table_name: Az adatbázis tábla neve (default: "dfv_smart_db")
    
    Returns:
        tuple: (co2_hourly_df, co2_hourly_with_power, daily_co2_df)
    """
    
    if api_key is None:
        return None, None, None
    
    # Dátumok számítása - először lekérdezzük az utolsó adatbázis napját
    try:
        last_date_query = f"SELECT MAX(date) as last_date FROM {table_name}"
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
                
                # Adatbázisból teljesítményadatok lekérdezése
                try:
                    # Oszlopnevek meghatározása a táblanév alapján
                    if table_name == "dfv_termosztat_db":
                        power_column = "trend_termosztat_p"
                    else:  # dfv_smart_db
                        power_column = "trend_smart_p"
                    
                    # Teljesítményadatok lekérése az adatbázisból (kW-ban van tárolva, de W-ban kezeljük) dátum-idővel
                    power_query = f"""
                    SELECT date, time, {power_column} as power_W
                    FROM {table_name}
                    WHERE date >= '{start_date.date()}' AND date <= '{end_date.date()}'
                    AND {power_column} IS NOT NULL
                    ORDER BY date, time
                    """
                    power_data = execute_query(power_query)
                    
                    if power_data:
                        # DataFrame létrehozása teljesítményadatokkal
                        power_df = pd.DataFrame(power_data, columns=['Dátum', 'Idő', 'Teljesítmény (W)'])
                        power_df['Dátum'] = pd.to_datetime(power_df['Dátum']).dt.date
                        power_df['Dátum_Idő'] = pd.to_datetime(power_df['Dátum'].astype(str) + ' ' + power_df['Idő'].astype(str))
                        
                        # Teljesítmény konvertálása float-ra (Decimal típusból) és kW-ból W-ra konvertálás (1000-el szorzás)
                        power_df['Teljesítmény (W)'] = pd.to_numeric(power_df['Teljesítmény (W)'], errors='coerce').astype(float) * 1000.0
                        
                        # Órásra kerekítés a CO2 intenzitással való párosításhoz (timezone nélkül)
                        power_df['Dátum_Idő_Óra'] = power_df['Dátum_Idő'].dt.floor('H').dt.tz_localize(None)
                        
                        # CO2 intenzitás DataFrame előkészítése merge-hoz
                        # Timezone eltávolítása vagy konvertálás, hogy kompatibilis legyen
                        if co2_hourly_df['Dátum és idő'].dt.tz is not None:
                            # Ha UTC timezone van, eltávolítjuk
                            co2_hourly_df['Dátum_Idő_Óra'] = co2_hourly_df['Dátum és idő'].dt.tz_localize(None).dt.floor('H')
                        else:
                            co2_hourly_df['Dátum_Idő_Óra'] = co2_hourly_df['Dátum és idő'].dt.floor('H')
                        
                        # CO2 intenzitás konvertálása float-ra (ha Decimal típusú)
                        co2_hourly_df['CO2 Kibocsátás (g CO2/kWh)'] = pd.to_numeric(co2_hourly_df['CO2 Kibocsátás (g CO2/kWh)'], errors='coerce').astype(float)
                        
                        # Adott teljesítményértékekhez az adott órához tartozó CO2 intenzitás
                        power_with_co2 = pd.merge(
                            power_df,
                            co2_hourly_df[['Dátum_Idő_Óra', 'CO2 Kibocsátás (g CO2/kWh)']],
                            on='Dátum_Idő_Óra',
                            how='inner'
                        )
                        
                        # CO2 kibocsátás számítása grammban minden egyedi teljesítményértékhez
                        # Mivel teljesítmény W-ban van, 1 óra alatt: energia (kWh) = teljesítmény (W) / 1000
                        # CO2 (g) = energia (kWh) * CO2 intenzitás (g CO2/kWh)
                        # Minden oszlop float típusú legyen
                        power_with_co2['Teljesítmény (W)'] = pd.to_numeric(power_with_co2['Teljesítmény (W)'], errors='coerce').astype(float)
                        power_with_co2['CO2 Kibocsátás (g CO2/kWh)'] = pd.to_numeric(power_with_co2['CO2 Kibocsátás (g CO2/kWh)'], errors='coerce').astype(float)
                        power_with_co2['Óras energia (kWh)'] = power_with_co2['Teljesítmény (W)'] / 1000.0
                        power_with_co2['CO2 (g)'] = power_with_co2['Óras energia (kWh)'] * power_with_co2['CO2 Kibocsátás (g CO2/kWh)']
                        
                        # Órás átlagos teljesítmény és összesített CO2 számítása (megjelenítéshez)
                        co2_hourly_with_power = power_with_co2.groupby('Dátum_Idő_Óra').agg({
                            'Teljesítmény (W)': 'mean',
                            'CO2 (g)': 'sum'
                        }).reset_index()
                        co2_hourly_with_power.columns = ['Dátum és idő', 'Óras átlagos teljesítmény (W)', 'Óras CO2 (g)']
                        co2_hourly_with_power['Dátum'] = co2_hourly_with_power['Dátum és idő'].dt.date
                        
                        # Minden egyedi teljesítményérték és hozzá tartozó CO2 kibocsátás (diagramhoz)
                        # Az adatbázisból közvetlenül kiolvasott teljesítményértékeket használjuk
                        power_co2_pairs = power_with_co2[['Teljesítmény (W)', 'CO2 (g)']].copy()
                        power_co2_pairs.columns = ['Teljesítmény (W)', 'CO2 (g)']
                        
                        # Napi adatok kiszámítása
                        # Napi átlagos teljesítmény (W) és összes CO2 (g)
                        daily_stats = power_with_co2.groupby('Dátum').agg({
                            'Teljesítmény (W)': 'mean',
                            'CO2 (g)': 'sum'
                        }).reset_index()
                        daily_stats.columns = ['Dátum', 'Napi átlagos teljesítmény (W)', 'Napi CO2 (g)']
                        
                        # Float típusra konvertálás
                        daily_stats['Napi átlagos teljesítmény (W)'] = pd.to_numeric(daily_stats['Napi átlagos teljesítmény (W)'], errors='coerce').astype(float)
                        daily_stats['Napi CO2 (g)'] = pd.to_numeric(daily_stats['Napi CO2 (g)'], errors='coerce').astype(float)
                        
                        # Napi energia (kWh) számítása
                        daily_stats['Napi energia (kWh)'] = (daily_stats['Napi átlagos teljesítmény (W)'] * 24.0) / 1000.0
                        
                        # Napi CO2 intenzitás
                        co2_daily_intensity = co2_hourly_df.groupby('Dátum')['CO2 Kibocsátás (g CO2/kWh)'].mean().reset_index()
                        co2_daily_intensity.columns = ['Dátum', 'Átlag CO2 (g CO2/kWh)']
                        
                        # Float típusra konvertálás
                        co2_daily_intensity['Átlag CO2 (g CO2/kWh)'] = pd.to_numeric(co2_daily_intensity['Átlag CO2 (g CO2/kWh)'], errors='coerce').astype(float)
                        
                        # Napi CO2 adatok kombinálása
                        daily_co2_df = pd.merge(daily_stats, co2_daily_intensity, on='Dátum', how='inner')
                        
                        # Float típusra konvertálás a számítások előtt
                        daily_co2_df['Napi energia (kWh)'] = pd.to_numeric(daily_co2_df['Napi energia (kWh)'], errors='coerce').astype(float)
                        daily_co2_df['Átlag CO2 (g CO2/kWh)'] = pd.to_numeric(daily_co2_df['Átlag CO2 (g CO2/kWh)'], errors='coerce').astype(float)
                        daily_co2_df['Napi CO2 (g)'] = pd.to_numeric(daily_co2_df['Napi CO2 (g)'], errors='coerce').astype(float)
                        
                        # Konvertálás datetime-re a megjelenítéshez
                        daily_co2_df['Dátum_datetime'] = pd.to_datetime(daily_co2_df['Dátum'])
                        
                        # Minden egyedi teljesítményérték és hozzá tartozó CO2 kibocsátás (diagramhoz)
                        # Visszaadjuk a power_co2_pairs-t is, hogy minden egyedi mérési pont látható legyen
                        power_co2_pairs = power_with_co2[['Teljesítmény (W)', 'CO2 (g)']].copy()
                        power_co2_pairs.columns = ['Teljesítmény (W)', 'CO2 (g)']
                        
                        return co2_hourly_df, co2_hourly_with_power, daily_co2_df, power_co2_pairs
                    else:
                        # Ha nincs energiaadat, akkor csak CO2 intenzitást ad vissza
                        return co2_hourly_df, None, None, None
                        
                except Exception as e:
                    st.error(f"Hiba az energiaadatok lekérdezésekor: {e}")
                    return co2_hourly_df, None, None, None
            else:
                st.warning("Nincs adat a kiválasztott időszakban.")
                return None, None, None, None
        else:
            st.error(f"API hiba: {response.status_code} - {response.text}")
            return None, None, None, None
            
    except Exception as e:
        st.error(f"Hiba történt az adatok lekérése során: {e}")
        return None, None, None, None


def fetch_co2_forecast_hourly(api_key, days=3):
    """
    Lekéri a CO2 kibocsátási előrejelzést az Electricity Maps API-ból óránkénti bontásban.
    Csak a következő 3 napra van előrejelzés elérhető.
    
    Args:
        api_key: API kulcs
        days: Hány napra előre kérdezze le (max 3, default: 3)
    
    Returns:
        DataFrame: CO2 intenzitás adatok óránkénti bontásban
    """
    
    if api_key is None:
        return None
    
    # Maximum 3 nap lehet
    days = min(3, days)
    
    # Forecast endpoint - óránkénti előrejelzés
    base_url = "https://api.electricitymaps.com/v3/carbon-intensity/forecast"
    api_url = f"{base_url}?zone=HU"
    
    try:
        response = requests.get(
            api_url,
            headers={"auth-token": api_key}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            co2_data = []
            
            # Ellenőrizzük a különböző lehetséges válaszformátumokat
            if 'forecast' in data and len(data['forecast']) > 0:
                forecast_items = data['forecast']
            elif isinstance(data, list) and len(data) > 0:
                forecast_items = data
            elif 'data' in data and len(data['data']) > 0:
                forecast_items = data['data']
            else:
                st.warning("Nincs előrejelzési adat az API válaszban.")
                return None
            
            # Csak az első 3 nap (72 óra) adatainak feldolgozása
            processed_hours = 0
            max_hours = days * 24
            
            for item in forecast_items:
                if processed_hours >= max_hours:
                    break
                
                # Dátum-idő kezelése
                if 'datetime' in item:
                    timestamp_str = item['datetime']
                elif 'dt' in item:
                    timestamp_str = item['dt']
                else:
                    continue
                
                try:
                    # Időbélyeg feldolgozása
                    timestamp_str_clean = timestamp_str.replace('Z', '')
                    if '+' in timestamp_str_clean:
                        timestamp_str_clean = timestamp_str_clean.split('+')[0]
                    timestamp = datetime.fromisoformat(timestamp_str_clean)
                except Exception:
                    continue
                
                # CO2 intenzitás kinyerése
                co2_intensity = item.get('carbonIntensity', item.get('value', item.get('intensity', 0)))
                
                if co2_intensity is not None and co2_intensity > 0:
                    co2_data.append({
                        'Dátum és idő': timestamp,
                        'CO2 Kibocsátás (g CO2/kWh)': co2_intensity,
                        'Dátum': timestamp.date(),
                        'Óra': timestamp.hour
                    })
                    processed_hours += 1
            
            if len(co2_data) > 0:
                co2_df = pd.DataFrame(co2_data)
                
                # Dátum szerint rendezés
                co2_df = co2_df.sort_values('Dátum és idő').reset_index(drop=True)
                
                return co2_df
            else:
                st.warning("Nem sikerült feldolgozni az előrejelzési adatokat.")
                return None
        else:
            st.error(f"API hiba: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Hiba történt az előrejelzési adatok lekérése során: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None

