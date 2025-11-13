import pandas as pd
from datetime import datetime, timedelta
from app_services.database import execute_query
import streamlit as st


def fetch_co2_emission_data(days_to_show=10, api_key=None, table_name="dfv_smart_db", heater_power=None):
    """
    Lekéri a CO2 kibocsátási adatokat fix CO2 intenzitás alapján
    és kombinálja az energiadataival az adatbázisból.
    
    Args:
        days_to_show: Hány napra visszamenőleg kérdezze le (default: 10)
        api_key: Nem használjuk (kompatibilitás miatt maradt)
        table_name: Az adatbázis tábla neve (default: "dfv_smart_db")
        heater_power: Fűtőteljesítmény (W) - ha meg van adva, arányosítja az adatbázis teljesítményét
    
    Returns:
        tuple: (co2_hourly_df, co2_hourly_with_power, daily_co2_df, power_co2_pairs)
    """
    
    # Fix CO2 intenzitás (g CO2/kWh)
    co2_intensity = 256.206
    
    # Dátumok számítása - lekérdezzük az első és utolsó adatbázis napját (összes nap)
    try:
        from page_modules.database_queries import get_last_date_from_table
        last_date_query = get_last_date_from_table(table_name)
        last_date_result = execute_query(last_date_query)
        if last_date_result and len(last_date_result) > 0 and last_date_result[0][0]:
            end_date = datetime.combine(last_date_result[0][0], datetime.max.time())
        else:
            end_date = datetime.now()
        
        # Első dátum lekérdezése
        first_date_query = f"SELECT MIN(date) as first_date FROM {table_name}"
        first_date_result = execute_query(first_date_query)
        if first_date_result and len(first_date_result) > 0 and first_date_result[0][0]:
            start_date = datetime.combine(first_date_result[0][0], datetime.min.time())
        else:
            # Ha nincs első dátum, akkor az utolsó dátumtól visszafelé days_to_show napot
            start_date = end_date - timedelta(days=days_to_show)
    except:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_to_show)
    
    # Órás CO2 intenzitás DataFrame létrehozása fix értékkel
    # Minden órára ugyanazt a fix értéket használjuk
    co2_hourly_data = []
    current_date = start_date
    while current_date <= end_date:
        # Minden órára létrehozunk egy bejegyzést
        for hour in range(24):
            timestamp = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            co2_hourly_data.append({
                'Dátum és idő': timestamp,
                'CO2 Kibocsátás (g CO2/kWh)': co2_intensity,
                'Dátum': timestamp.date()
            })
        current_date += timedelta(days=1)
        # Ha elérjük az end_date napját, csak az adott nap óráit adjuk hozzá
        if current_date.date() > end_date.date():
            break
    
    co2_hourly_df = pd.DataFrame(co2_hourly_data)
    
    try:
        # Teljesítmény adatok lekérdezése
        from page_modules.database_queries import get_power_data_for_co2
        power_query = get_power_data_for_co2(
            table_name, 
            str(start_date.date()), 
            str(end_date.date())
        )
        power_data = execute_query(power_query)
        
        if power_data:
            # DataFrame létrehozása teljesítményadatokkal
            power_df = pd.DataFrame(power_data, columns=['Dátum', 'Idő', 'Teljesítmény (W)'])
            power_df['Dátum'] = pd.to_datetime(power_df['Dátum']).dt.date
            power_df['Dátum_Idő'] = pd.to_datetime(power_df['Dátum'].astype(str) + ' ' + power_df['Idő'].astype(str))
            
            power_df['Teljesítmény (W)'] = pd.to_numeric(power_df['Teljesítmény (W)'], errors='coerce').astype(float) * 1000.0
            
            # Ha van fűtőteljesítmény megadva, arányosítjuk az adatbázis teljesítményét
            if heater_power is not None and heater_power > 0:
                # Arány számítása: adatbázis_teljesítmény / fűtőteljesítmény
                power_df['Arány'] = power_df['Teljesítmény (W)'] / heater_power
                # Arányosított teljesítmény = fűtőteljesítmény * arány (ami ugyanaz, mint az adatbázis teljesítmény)
                # De a CO2 számításnál az arányt használjuk
                power_df['Arányosított_teljesítmény'] = heater_power * power_df['Arány']
            else:
                power_df['Arány'] = 1.0
                power_df['Arányosított_teljesítmény'] = power_df['Teljesítmény (W)']
            
            power_df = power_df.sort_values('Dátum_Idő').reset_index(drop=True)
            
            #Mérések közti idő kiszámítása
            power_df['Következő_Dátum_Idő'] = power_df['Dátum_Idő'].shift(-1)
            power_df['Időköz_óra'] = (power_df['Következő_Dátum_Idő'] - power_df['Dátum_Idő']).dt.total_seconds() / 3600.0
            
            avg_interval = power_df['Időköz_óra'].dropna().mean()
            power_df['Időköz_óra'] = power_df['Időköz_óra'].fillna(avg_interval if not pd.isna(avg_interval) else 1.0)
            
            # Órásra kerekítés a CO2 intenzitással való párosításhoz (timezone nélkül)
            power_df['Dátum_Idő_Óra'] = power_df['Dátum_Idő'].dt.floor('H').dt.tz_localize(None)
            
            # CO2 intenzitás DataFrame
            if co2_hourly_df['Dátum és idő'].dt.tz is not None:
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
            
            # Dátum oszlop hozzáadása a Dátum_Idő-ből (ha nincs benne)
            if 'Dátum' not in power_with_co2.columns:
                power_with_co2['Dátum'] = power_with_co2['Dátum_Idő'].dt.date
            
            # CO2 kibocsátás számítása grammban minden egyedi teljesítményértékhez
            # Ha van fűtőteljesítmény, az arányosított teljesítményt használjuk
            power_with_co2['Teljesítmény (W)'] = pd.to_numeric(power_with_co2['Teljesítmény (W)'], errors='coerce').astype(float)
            power_with_co2['CO2 Kibocsátás (g CO2/kWh)'] = pd.to_numeric(power_with_co2['CO2 Kibocsátás (g CO2/kWh)'], errors='coerce').astype(float)
            power_with_co2['Időköz_óra'] = pd.to_numeric(power_with_co2['Időköz_óra'], errors='coerce').astype(float)
            
            # Ha van arányosított teljesítmény oszlop, azt használjuk, különben az eredeti teljesítményt
            if 'Arányosított_teljesítmény' in power_with_co2.columns:
                power_with_co2['Számítási_teljesítmény'] = pd.to_numeric(power_with_co2['Arányosított_teljesítmény'], errors='coerce').astype(float)
            else:
                power_with_co2['Számítási_teljesítmény'] = power_with_co2['Teljesítmény (W)']

            # Energia (kWh) = arányosított teljesítmény (W) * időköz (óra) / 1000
            # CO2 (g) = energia (kWh) * CO2 intenzitás (g CO2/kWh)
            power_with_co2['Energia (kWh)'] = (power_with_co2['Számítási_teljesítmény'] * power_with_co2['Időköz_óra']) / 1000.0
            power_with_co2['CO2 (g)'] = power_with_co2['Energia (kWh)'] * power_with_co2['CO2 Kibocsátás (g CO2/kWh)']
            
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
            # Első és utolsó mérés ideje, átlagos teljesítmény, mérések száma
            daily_stats = power_with_co2.groupby('Dátum').agg({
                'Teljesítmény (W)': ['mean', 'count'],
                'Dátum_Idő': ['min', 'max']  # Első és utolsó mérés ideje
            }).reset_index()
            
            # Oszlopnevek javítása
            daily_stats.columns = ['Dátum', 'Napi átlagos teljesítmény (W)', 'Mérések_száma', 'Első_mérés', 'Utolsó_mérés']
            
            # Működési órák számítása (első és utolsó mérés közötti idő)
            daily_stats['Működési_óra'] = (daily_stats['Utolsó_mérés'] - daily_stats['Első_mérés']).dt.total_seconds() / 3600.0
            
            # Fogyasztás számítása: átlagos teljesítmény × működési órák / 1000
            daily_stats['Napi energia (kWh)'] = (daily_stats['Napi átlagos teljesítmény (W)'] * daily_stats['Működési_óra']) / 1000.0
            
            # CO2 kibocsátás számítása: fogyasztás × CO2 intenzitás
            daily_stats['Napi CO2 (g)'] = daily_stats['Napi energia (kWh)'] * co2_intensity
            
            # Felesleges oszlopok eltávolítása
            daily_stats = daily_stats.drop(columns=['Első_mérés', 'Utolsó_mérés'])
            
            # Float típusra konvertálás
            daily_stats['Napi átlagos teljesítmény (W)'] = pd.to_numeric(daily_stats['Napi átlagos teljesítmény (W)'], errors='coerce').astype(float)
            daily_stats['Napi energia (kWh)'] = pd.to_numeric(daily_stats['Napi energia (kWh)'], errors='coerce').astype(float)
            daily_stats['Napi CO2 (g)'] = pd.to_numeric(daily_stats['Napi CO2 (g)'], errors='coerce').astype(float)
            daily_stats['Működési_óra'] = pd.to_numeric(daily_stats['Működési_óra'], errors='coerce').astype(float)
            
            # Napi CO2 adatok (már nincs szükség a CO2 intenzitásra)
            daily_co2_df = daily_stats.copy()
            
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

