import pandas as pd
from datetime import datetime, timedelta
from app_services.database import execute_query
import streamlit as st

"Lekérdezzük az adatbázisban megtalálható első és utolsó dátumot."
def _get_date_range(table_name, days_to_show):
    try:
        from page_modules.database_queries import get_last_date_from_table
        last_date_query = get_last_date_from_table(table_name)
        last_date_result = execute_query(last_date_query)
        if last_date_result and len(last_date_result) > 0 and last_date_result[0][0]:
            end_date = datetime.combine(last_date_result[0][0], datetime.max.time())
        else:
            end_date = datetime.now()
        
        first_date_query = f"SELECT MIN(date) as first_date FROM {table_name}"
        first_date_result = execute_query(first_date_query)
        if first_date_result and len(first_date_result) > 0 and first_date_result[0][0]:
            start_date = datetime.combine(first_date_result[0][0], datetime.min.time())
        else:
            start_date = end_date - timedelta(days=days_to_show)
        return start_date, end_date
    except:
        end_date = datetime.now()
        return end_date - timedelta(days=days_to_show), end_date

"Legenerálja a CO2 intenzitás adatokat óránként."
def _create_co2_hourly_df(start_date, end_date, co2_intensity):
    co2_hourly_data = []
    current_date = start_date
    while current_date <= end_date:
        for hour in range(24):
            timestamp = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            co2_hourly_data.append({
                'Dátum és idő': timestamp,
                'CO2 Kibocsátás (g CO2/kWh)': co2_intensity,
                'Dátum': timestamp.date()
            })
        current_date += timedelta(days=1)
        if current_date.date() > end_date.date():
            break
    return pd.DataFrame(co2_hourly_data)

    "Teljesítmény adatok előkészítése."
def _prepare_power_df(power_data, heater_power):
    power_df = pd.DataFrame(power_data, columns=['Dátum', 'Idő', 'Teljesítmény (kW)'])
    power_df['Dátum'] = pd.to_datetime(power_df['Dátum']).dt.date
    power_df['Dátum_Idő'] = pd.to_datetime(power_df['Dátum'].astype(str) + ' ' + power_df['Idő'].astype(str))
    power_df['Teljesítmény (kW)'] = pd.to_numeric(power_df['Teljesítmény (kW)'], errors='coerce').astype(float)
    
    if heater_power is not None and heater_power > 0:
        heater_power_kw = heater_power / 1000.0
        power_df['Arány'] = power_df['Teljesítmény (kW)'] / heater_power_kw
        power_df['Arányosított_teljesítmény'] = heater_power_kw * power_df['Arány']
    else:
        power_df['Arány'] = 1.0
        power_df['Arányosított_teljesítmény'] = power_df['Teljesítmény (kW)']
    
    power_df = power_df.sort_values('Dátum_Idő').reset_index(drop=True)
    
    power_df['Következő_Dátum_Idő'] = power_df['Dátum_Idő'].shift(-1)
    power_df['Időköz_óra'] = (power_df['Következő_Dátum_Idő'] - power_df['Dátum_Idő']).dt.total_seconds() / 3600.0
    avg_interval = power_df['Időköz_óra'].dropna().mean()
    power_df['Időköz_óra'] = power_df['Időköz_óra'].fillna(avg_interval if not pd.isna(avg_interval) else 1.0)
    power_df['Dátum_Idő_Óra'] = power_df['Dátum_Idő'].dt.floor('H').dt.tz_localize(None)
    
    return power_df

"Összeköti a teljesítmény adatokat a CO2 intenzitással, majd ellenőrzi, hogy a dátum és idő oszlopok megegyeznek-e."
def _merge_power_with_co2(power_df, co2_hourly_df):
    if co2_hourly_df['Dátum és idő'].dt.tz is not None:
        co2_hourly_df['Dátum_Idő_Óra'] = co2_hourly_df['Dátum és idő'].dt.tz_localize(None).dt.floor('H')
    else:
        co2_hourly_df['Dátum_Idő_Óra'] = co2_hourly_df['Dátum és idő'].dt.floor('H')
    
    co2_hourly_df['CO2 Kibocsátás (g CO2/kWh)'] = pd.to_numeric(
        co2_hourly_df['CO2 Kibocsátás (g CO2/kWh)'], errors='coerce'
    ).astype(float)
    
    power_with_co2 = pd.merge(
        power_df,
        co2_hourly_df[['Dátum_Idő_Óra', 'CO2 Kibocsátás (g CO2/kWh)']],
        on='Dátum_Idő_Óra',
        how='inner'
    )
    
    if 'Dátum' not in power_with_co2.columns:
        power_with_co2['Dátum'] = power_with_co2['Dátum_Idő'].dt.date
    
    return power_with_co2

"CO2 kibocsátás kiszámítása."
def _calculate_co2_emissions(power_with_co2):
    power_with_co2['Teljesítmény (kW)'] = pd.to_numeric(
        power_with_co2['Teljesítmény (kW)'], errors='coerce'
    ).astype(float)
    power_with_co2['CO2 Kibocsátás (g CO2/kWh)'] = pd.to_numeric(
        power_with_co2['CO2 Kibocsátás (g CO2/kWh)'], errors='coerce'
    ).astype(float)
    power_with_co2['Időköz_óra'] = pd.to_numeric(
        power_with_co2['Időköz_óra'], errors='coerce'
    ).astype(float)
    
    if 'Arányosított_teljesítmény' in power_with_co2.columns:
        power_with_co2['Számítási_teljesítmény'] = pd.to_numeric(
            power_with_co2['Arányosított_teljesítmény'], errors='coerce'
        ).astype(float)
    else:
        power_with_co2['Számítási_teljesítmény'] = power_with_co2['Teljesítmény (kW)']
    
    power_with_co2['Energia (kWh)'] = power_with_co2['Számítási_teljesítmény'] * power_with_co2['Időköz_óra']
    power_with_co2['CO2 (g)'] = power_with_co2['Energia (kWh)'] * power_with_co2['CO2 Kibocsátás (g CO2/kWh)']
    
    return power_with_co2


"Órás összesített adatok létrehozása."
def _create_hourly_summary(power_with_co2):
    co2_hourly_with_power = power_with_co2.groupby('Dátum_Idő_Óra').agg({
        'Teljesítmény (kW)': 'mean',
        'CO2 (g)': 'sum'
    }).reset_index()
    co2_hourly_with_power.columns = ['Dátum és idő', 'Óras átlagos teljesítmény (kW)', 'Óras CO2 (g)']
    co2_hourly_with_power['Dátum'] = co2_hourly_with_power['Dátum és idő'].dt.date
    return co2_hourly_with_power


"Napi statisztikák létrehozása."
def _create_daily_stats(power_with_co2, co2_intensity):
    daily_stats = power_with_co2.groupby('Dátum').agg({
        'Teljesítmény (kW)': ['mean', 'sum', 'count'],
        'Dátum_Idő': ['min', 'max']
    }).reset_index()
    
    daily_stats.columns = [
        'Dátum', 'Napi átlagos teljesítmény (kW)', 'Napi összes teljesítmény (kW)',
        'Mérések_száma', 'Első_mérés', 'Utolsó_mérés'
    ]
    
    daily_stats['Működési_óra'] = (
        daily_stats['Utolsó_mérés'] - daily_stats['Első_mérés']
    ).dt.total_seconds() / 3600.0
    daily_stats['Napi energia (kWh)'] = daily_stats['Napi összes teljesítmény (kW)'] * 0.25
    daily_stats['Napi CO2 (g)'] = daily_stats['Napi energia (kWh)'] * co2_intensity
    
    daily_stats = daily_stats.drop(columns=['Első_mérés', 'Utolsó_mérés', 'Napi összes teljesítmény (kW)'])
    
    daily_stats['Napi átlagos teljesítmény (kW)'] = pd.to_numeric(
        daily_stats['Napi átlagos teljesítmény (kW)'], errors='coerce'
    ).astype(float)
    daily_stats['Napi energia (kWh)'] = pd.to_numeric(
        daily_stats['Napi energia (kWh)'], errors='coerce'
    ).astype(float)
    daily_stats['Napi CO2 (g)'] = pd.to_numeric(
        daily_stats['Napi CO2 (g)'], errors='coerce'
    ).astype(float)
    daily_stats['Működési_óra'] = pd.to_numeric(
        daily_stats['Működési_óra'], errors='coerce'
    ).astype(float)
    
    daily_co2_df = daily_stats.copy()
    daily_co2_df['Dátum_datetime'] = pd.to_datetime(daily_co2_df['Dátum'])
    
    return daily_co2_df

"Lekéri a CO2 kibocsátási adatokat a CO2 intenzitás alapján, majd összeköti az adatokkal az adatbázisból."
def fetch_co2_emission_data(days_to_show=10, api_key=None, table_name="dfv_smart_db", heater_power=None):
    co2_intensity = 190.0
    
    start_date, end_date = _get_date_range(table_name, days_to_show)
    co2_hourly_df = _create_co2_hourly_df(start_date, end_date, co2_intensity)
    
    try:
        from page_modules.database_queries import get_power_data_for_co2
        power_query = get_power_data_for_co2(
            table_name, 
            str(start_date.date()), 
            str(end_date.date())
        )
        power_data = execute_query(power_query)
        
        if not power_data:
            return co2_hourly_df, None, None, None
        
        power_df = _prepare_power_df(power_data, heater_power)
        power_with_co2 = _merge_power_with_co2(power_df, co2_hourly_df)
        power_with_co2 = _calculate_co2_emissions(power_with_co2)
        
        co2_hourly_with_power = _create_hourly_summary(power_with_co2)
        daily_co2_df = _create_daily_stats(power_with_co2, co2_intensity)
        power_co2_pairs = power_with_co2[['Teljesítmény (kW)', 'CO2 (g)']].copy()
        
        return co2_hourly_df, co2_hourly_with_power, daily_co2_df, power_co2_pairs
        
    except Exception as e:
        st.error(f"Hiba az energiaadatok lekérdezésekor: {e}")
        return co2_hourly_df, None, None, None
