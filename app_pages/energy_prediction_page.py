import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from app_services.eon_scraper import scrape_eon_prices, calculate_energy_costs


try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
    from statsmodels.tsa.seasonal import seasonal_decompose
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False

from app_services.database import get_db_connection, test_db_connection, execute_query

def show_energy_prediction_page():
    

    with open('styles.css', 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    st.markdown(f"""
    <style>
    {css_content}
    </style>
    """, unsafe_allow_html=True)
    
    st.write("# Energiafogyasztás és megtakarítás előrejelzés")
    
    # E.ON árak státusz megjelenítése
    if 'loss_prices' in st.session_state and st.session_state.loss_prices is not None:
        st.success("✅ Árak elérhetők")
    elif 'eon_error' in st.session_state and st.session_state.eon_error:
        st.error(f"❌ E.ON árak lekérése sikertelen: {st.session_state.eon_error}")
    else:
        st.warning("⚠️ E.ON árak nem érhetők el")
    
    st.write("---")
    
    # Database connection test
    if st.button("Adatbázis teszt"):
        if test_db_connection():
            st.success("Sikeres csatlakozás")
        else:
            st.error("Sikertelen csatlakozás")
    
    st.write("---")
    
    # Session state inicializálása
    if "arima_model_trained" not in st.session_state:
        st.session_state.arima_model_trained = False
    if "arima_model" not in st.session_state:
        st.session_state.arima_model = None
    if "arima_data" not in st.session_state:
        st.session_state.arima_data = None
    

    st.write("## Adatok kiválasztása")
    
    # Csak a dinamikus fűtésvezérlő használata
    selected_table = "dfv_smart_db"
    

    st.write("---")
    st.write("## Előrejelzés típusa")
    
    # Előrejelzés típusának kiválasztása
    forecast_type = st.selectbox(
        "Válassz előrejelzési típust:",
        options=["havi", "negyedéves", "féléves", "éves"],
        key="forecast_type_selector"
    )
    
    # Időszak kiválasztó a típus alapján
    selected_period = None
    forecast_start_date = None
    forecast_end_date = None
    
    if forecast_type == "havi":
        # Havi előrejelzés: hónap kiválasztása
        month_names = ["Január", "Február", "Március", "Április", "Május", "Június",
                      "Július", "Augusztus", "Szeptember", "Október", "November", "December"]
        
        selected_month_name = st.selectbox(
            "Válassz hónapot:",
            options=month_names,
            key="month_selector"
        )
        
        # Hónap számának meghatározása
        selected_month = month_names.index(selected_month_name) + 1
        selected_period = f"{selected_month:02d}"
        
        st.session_state.selected_month = selected_month
        
        forecast_year = 2026
        forecast_start_date = datetime(forecast_year, selected_month, 1)
        # Hónap utolsó napjának meghatározása
        if selected_month == 12:
            forecast_end_date = datetime(forecast_year, 12, 31)
        else:
            forecast_end_date = datetime(forecast_year, selected_month + 1, 1) - timedelta(days=1)
        
    elif forecast_type == "negyedéves":
        # Negyedéves előrejelzés: negyedév kiválasztása
        quarter_names = [
            "1. negyedév (Január-Március)",
            "2. negyedév (Április-Június)",
            "3. negyedév (Július-Szeptember)",
            "4. negyedév (Október-December)"
        ]
        
        selected_quarter_name = st.selectbox(
            "Válassz negyedévet:",
            options=quarter_names,
            key="quarter_selector"
        )
        
        # Negyedév számának meghatározása
        if "1. negyedév" in selected_quarter_name:
            selected_quarter = 1
        elif "2. negyedév" in selected_quarter_name:
            selected_quarter = 2
        elif "3. negyedév" in selected_quarter_name:
            selected_quarter = 3
        else:  # 4. negyedév
            selected_quarter = 4
        
        selected_period = f"Q{selected_quarter}"
        
        # Session state-be mentés, hogy a gomb megnyomása után is elérhető legyen
        st.session_state.selected_quarter = selected_quarter
        
        # Negyedév dátumainak meghatározása
        forecast_year = 2026
        if selected_quarter == 1:
            forecast_start_date = datetime(forecast_year, 1, 1)
            forecast_end_date = datetime(forecast_year, 3, 31)
        elif selected_quarter == 2:
            forecast_start_date = datetime(forecast_year, 4, 1)
            forecast_end_date = datetime(forecast_year, 6, 30)
        elif selected_quarter == 3:
            forecast_start_date = datetime(forecast_year, 7, 1)
            forecast_end_date = datetime(forecast_year, 9, 30)
        else:  # 4. negyedév
            forecast_start_date = datetime(forecast_year, 10, 1)
            forecast_end_date = datetime(forecast_year, 12, 31)
            
    elif forecast_type == "féléves":
        # Féléves előrejelzés: félév kiválasztása
        semester_names = [
            "1. félév (Január-Június)",
            "2. félév (Július-December)"
        ]
        
        selected_semester_name = st.selectbox(
            "Válassz félévet:",
            options=semester_names,
            key="semester_selector"
        )
        
        # Félév számának meghatározása
        if "1. félév" in selected_semester_name:
            selected_semester = 1
        else:  # 2. félév
            selected_semester = 2
        
        selected_period = f"S{selected_semester}"
        
        # Session state-be mentés, hogy a gomb megnyomása után is elérhető legyen
        st.session_state.selected_semester = selected_semester
        
        # Félév dátumainak meghatározása
        forecast_year = 2026
        if selected_semester == 1:
            forecast_start_date = datetime(forecast_year, 1, 1)
            forecast_end_date = datetime(forecast_year, 6, 30)
        else:  # 2. félév
            forecast_start_date = datetime(forecast_year, 7, 1)
            forecast_end_date = datetime(forecast_year, 12, 31)
            
    else:  # éves
        forecast_start_date = datetime(2026, 1, 1)
        forecast_end_date = datetime(2026, 12, 31)
        selected_period = "2026"
    
    # Előrejelzés generálása
    if st.button("Előrejelzés generálása", type="primary"):
        with st.spinner("Adatok betöltése és előrejelzés generálása folyamatban..."):
            try:
                # Oszlopnevek meghatározása
                power_column = "trend_smart_p" if selected_table == "dfv_smart_db" else "trend_termosztat_p"
                current_column = "trend_smart_i1" if selected_table == "dfv_smart_db" else "trend_termosztat_i1"
                temp_column = "trend_smart_t" if selected_table == "dfv_smart_db" else "trend_termosztat_t"
                humidity_column = "trend_smart_rh" if selected_table == "dfv_smart_db" else "trend_termosztat_rh"
                
                # Adatbázisból történeti adatok lekérdezése a megfelelő időszakhoz
                data = None  # Inicializálás
                
                if forecast_type == "havi":
                    # Session state-ből lekérdezés a selected_month értékére
                    if 'selected_month' not in st.session_state:
                        st.error("Hiba: Kérjük, válasszon hónapot az előrejelzéshez!")
                        st.stop()
                    
                    selected_month_value = st.session_state.selected_month
                    
                    # Ugyanazon hónap keresése az előző évekből
                    if selected_month_value == 5:  # Május
                        start_date = "2025-05-01"
                        end_date = "2025-05-31"
                        query = f"""
                        SELECT date, time, 
                               {power_column} as value,
                               {current_column} as current,
                               {temp_column} as internal_temp,
                               trend_kulso_homerseklet_pillanatnyi as external_temp,
                               {humidity_column} as internal_humidity,
                               trend_kulso_paratartalom as external_humidity
                        FROM {selected_table}
                        WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
                        AND {power_column} IS NOT NULL 
                        AND {current_column} IS NOT NULL
                        AND {temp_column} IS NOT NULL
                        AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                        ORDER BY date, time
                        """
                        data = execute_query(query)
                    else:
                        # Minden más hónap esetén minden évből
                        query = f"""
                        SELECT date, time, 
                               {power_column} as value,
                               {current_column} as current,
                               {temp_column} as internal_temp,
                               trend_kulso_homerseklet_pillanatnyi as external_temp,
                               {humidity_column} as internal_humidity,
                               trend_kulso_paratartalom as external_humidity
                        FROM {selected_table}
                        WHERE EXTRACT(MONTH FROM date) = {selected_month_value}
                        AND {power_column} IS NOT NULL 
                        AND {current_column} IS NOT NULL
                        AND {temp_column} IS NOT NULL
                        AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                        ORDER BY date, time
                        """
                        data = execute_query(query)
                elif forecast_type == "negyedéves":
                    # Session state-ből lekérdezés a selected_quarter értékére
                    if 'selected_quarter' not in st.session_state:
                        st.error("Hiba: Kérjük, válasszon negyedévet az előrejelzéshez!")
                        st.stop()
                    
                    selected_quarter = st.session_state.selected_quarter
                    
    
                    if selected_quarter == 1:
                        month_numbers = [1, 2, 3]  # Január, február, március
                    elif selected_quarter == 2:
                        month_numbers = [4, 5, 6]  # Április, május, június
                    elif selected_quarter == 3:
                        month_numbers = [7, 8, 9]  # Július, augusztus, szeptember
                    else:  # 4. negyedév
                        month_numbers = [10, 11, 12]  # Október, november, december
                    
                    month_list = ','.join(map(str, month_numbers))
                    query = f"""
                    SELECT date, time, 
                           {power_column} as value,
                           {current_column} as current,
                           {temp_column} as internal_temp,
                           trend_kulso_homerseklet_pillanatnyi as external_temp,
                           {humidity_column} as internal_humidity,
                           trend_kulso_paratartalom as external_humidity
                    FROM {selected_table}
                    WHERE EXTRACT(MONTH FROM date) IN ({month_list})
                    AND {power_column} IS NOT NULL 
                    AND {current_column} IS NOT NULL
                    AND {temp_column} IS NOT NULL
                    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                    ORDER BY date, time
                    """
                    data = execute_query(query)
                elif forecast_type == "féléves":
                    # Session state-ből lekérdezés a selected_semester értékére
                    if 'selected_semester' not in st.session_state:
                        st.error("Hiba: Kérjük, válasszon félévet az előrejelzéshez!")
                        st.stop()
                    
                    selected_semester = st.session_state.selected_semester
                    
                    # Ugyanazon félév keresése az előző évekből - hónap számok alapján
                    # 1. félév = január(1), február(2), március(3), április(4), május(5), június(6)
                    # 2. félév = július(7), augusztus(8), szeptember(9), október(10), november(11), december(12)
                    if selected_semester == 1:
                        month_numbers = [1, 2, 3, 4, 5, 6]  # Január - június
                    else:  # 2. félév
                        month_numbers = [7, 8, 9, 10, 11, 12]  # Július - december
                    
                    month_list = ','.join(map(str, month_numbers))
                    query = f"""
                    SELECT date, time, 
                           {power_column} as value,
                           {current_column} as current,
                           {temp_column} as internal_temp,
                           trend_kulso_homerseklet_pillanatnyi as external_temp,
                           {humidity_column} as internal_humidity,
                           trend_kulso_paratartalom as external_humidity
                    FROM {selected_table}
                    WHERE EXTRACT(MONTH FROM date) IN ({month_list})
                    AND {power_column} IS NOT NULL 
                    AND {current_column} IS NOT NULL
                    AND {temp_column} IS NOT NULL
                    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                    ORDER BY date, time
                    """
                    data = execute_query(query)
                else:  # éves
                    # Az összes elérhető adatot használjuk az előrejelzéshez
                    query = f"""
                    SELECT date, time, 
                           {power_column} as value,
                           {current_column} as current,
                           {temp_column} as internal_temp,
                           trend_kulso_homerseklet_pillanatnyi as external_temp,
                           {humidity_column} as internal_humidity,
                           trend_kulso_paratartalom as external_humidity
                    FROM {selected_table}
                    WHERE {power_column} IS NOT NULL 
                    AND {current_column} IS NOT NULL
                    AND {temp_column} IS NOT NULL
                    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                    ORDER BY date, time
                    """
                    data = execute_query(query)
                    
                if data and len(data) > 0:
                    # DataFrame létrehozása
                    df = pd.DataFrame(data, columns=['date', 'time', 'value', 'current', 
                                                    'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
                    
                    # Dátum-idő kombinálása
                    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
                    
                    # Numerikus értékek konvertálása
                    df['value'] = pd.to_numeric(df['value'], errors='coerce')
                    df['internal_temp'] = pd.to_numeric(df['internal_temp'], errors='coerce')
                    df['external_temp'] = pd.to_numeric(df['external_temp'], errors='coerce')
                    df['internal_humidity'] = pd.to_numeric(df['internal_humidity'], errors='coerce')
                    df['external_humidity'] = pd.to_numeric(df['external_humidity'], errors='coerce')
                    
                    # Hiányzó értékek eltávolítása
                    df = df.dropna(subset=['value'])
                    
                    # Rendezés dátum szerint
                    df = df.sort_values('datetime').reset_index(drop=True)
                    
                    # Május esetén: éves átlag számítása hiányzó napokhoz
                    has_may_data = False
                    if forecast_type == "havi" and 'selected_month' in st.session_state and st.session_state.selected_month == 5:
                        has_may_data = True
                    elif forecast_type == "negyedéves" and 'selected_quarter' in st.session_state and st.session_state.selected_quarter == 2:
                        has_may_data = True
                    elif forecast_type == "féléves" and 'selected_semester' in st.session_state and st.session_state.selected_semester == 1:
                        has_may_data = True
                    elif forecast_type == "éves":
                        has_may_data = True
                    
                    yearly_avg_value = None
                    yearly_avg_internal_temp = None
                    yearly_avg_external_temp = None
                    yearly_avg_internal_humidity = None
                    yearly_avg_external_humidity = None
                    
                    if has_may_data:
                        # Egész éves adatok lekérdezése az átlag számításához
                        yearly_query = f"""
                        SELECT date, time, 
                               {power_column} as value,
                               {current_column} as current,
                               {temp_column} as internal_temp,
                               trend_kulso_homerseklet_pillanatnyi as external_temp,
                               {humidity_column} as internal_humidity,
                               trend_kulso_paratartalom as external_humidity
                        FROM {selected_table}
                        WHERE {power_column} IS NOT NULL 
                        AND {current_column} IS NOT NULL
                        AND {temp_column} IS NOT NULL
                        AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
                        ORDER BY date, time
                        """
                        yearly_data = execute_query(yearly_query)
                        
                        if yearly_data and len(yearly_data) > 0:
                            yearly_df = pd.DataFrame(yearly_data, columns=['date', 'time', 'value', 'current', 
                                                                          'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
                            yearly_df['value'] = pd.to_numeric(yearly_df['value'], errors='coerce')
                            yearly_df['internal_temp'] = pd.to_numeric(yearly_df['internal_temp'], errors='coerce')
                            yearly_df['external_temp'] = pd.to_numeric(yearly_df['external_temp'], errors='coerce')
                            yearly_df['internal_humidity'] = pd.to_numeric(yearly_df['internal_humidity'], errors='coerce')
                            yearly_df['external_humidity'] = pd.to_numeric(yearly_df['external_humidity'], errors='coerce')
                            yearly_df = yearly_df.dropna(subset=['value'])
                            
                            # Dátum-idő kombinálása
                            yearly_df['datetime'] = pd.to_datetime(yearly_df['date'].astype(str) + ' ' + yearly_df['time'].astype(str))
                            yearly_df['date'] = yearly_df['datetime'].dt.date
                            
                            # Napi fogyasztás számítása: összeadom a negyedórás kW értékeket és megszorzom 0,25-el
                            yearly_daily_consumption = yearly_df.groupby('date')['value'].sum() * 0.25
                            
                            # Éves átlagok számítása (napi fogyasztás átlaga kWh-ban)
                            yearly_avg_value = yearly_daily_consumption.mean()
                            yearly_avg_internal_temp = yearly_df.groupby('date')['internal_temp'].mean().mean()
                            yearly_avg_external_temp = yearly_df.groupby('date')['external_temp'].mean().mean()
                            yearly_avg_internal_humidity = yearly_df.groupby('date')['internal_humidity'].mean().mean()
                            yearly_avg_external_humidity = yearly_df.groupby('date')['external_humidity'].mean().mean()
                    
                    # Napi fogyasztás számítása: összeadom a negyedórás kW értékeket és megszorzom 0,25-el
                    df['date'] = df['datetime'].dt.date
                    # Napi fogyasztás (kWh) = sum(kW) * 0.25
                    daily_consumption = df.groupby('date')['value'].sum() * 0.25
                    # Egyéb változók átlaga (hőmérséklet, páratartalom)
                    daily_df = df.groupby('date').agg({
                        'internal_temp': 'mean',
                        'external_temp': 'mean',
                        'internal_humidity': 'mean',
                        'external_humidity': 'mean'
                    }).reset_index()
                    # Napi fogyasztás hozzáadása (kWh-ban)
                    daily_df['value'] = daily_consumption.values
                    daily_df['datetime'] = pd.to_datetime(daily_df['date'])
                    daily_df = daily_df.drop('date', axis=1)
                    daily_df = daily_df.sort_values('datetime').reset_index(drop=True)
                    
                    # Május esetén: hiányzó napok kitöltése éves átlaggal
                    if has_may_data and yearly_avg_value is not None:
                        # Május összes napjának listája
                        may_start = datetime(2025, 5, 1)
                        may_end = datetime(2025, 5, 31)
                        all_may_dates = pd.date_range(start=may_start, end=may_end, freq='D')
                        
                        # Ellenőrizzük, hogy a daily_df tartalmaz-e májusi dátumokat
                        may_dates_in_data = daily_df[daily_df['datetime'].dt.month == 5]
                        
                        if len(may_dates_in_data) > 0 or forecast_type == "havi":
                            # Teljes májusi DataFrame létrehozása
                            complete_may_df = pd.DataFrame({
                                'datetime': all_may_dates
                            })
                            
                            # Meglévő májusi adatok kinyerése
                            may_data_from_daily = daily_df[daily_df['datetime'].dt.month == 5][['datetime', 'value', 'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity']]
                            
                            # Meglévő adatok egyesítése
                            complete_may_df = complete_may_df.merge(
                                may_data_from_daily,
                                on='datetime',
                                how='left'
                            )
                            
                            # Hiányzó napok számának meghatározása kitöltés előtt
                            missing_days_count = complete_may_df['value'].isna().sum()
                            
                            # Hiányzó értékek kitöltése éves átlaggal
                            complete_may_df['value'] = complete_may_df['value'].fillna(yearly_avg_value)
                            complete_may_df['internal_temp'] = complete_may_df['internal_temp'].fillna(yearly_avg_internal_temp)
                            complete_may_df['external_temp'] = complete_may_df['external_temp'].fillna(yearly_avg_external_temp)
                            complete_may_df['internal_humidity'] = complete_may_df['internal_humidity'].fillna(yearly_avg_internal_humidity)
                            complete_may_df['external_humidity'] = complete_may_df['external_humidity'].fillna(yearly_avg_external_humidity)
                            
                            # Rendezés
                            complete_may_df = complete_may_df.sort_values('datetime').reset_index(drop=True)
                            
                            # A teljes májusi DataFrame egyesítése a többi adattal
                            # Először eltávolítjuk a májusi napokat a daily_df-ből
                            daily_df_without_may = daily_df[daily_df['datetime'].dt.month != 5]
                            
                            # Összevonjuk a teljes májusi adatokat a többi adattal
                            daily_df = pd.concat([daily_df_without_may, complete_may_df], ignore_index=True)
                            daily_df = daily_df.sort_values('datetime').reset_index(drop=True)
                            
                            # Info üzenet
                            if missing_days_count > 0:
                                st.info(f"ℹ️ Májusi adatok: {len(complete_may_df)} nap (összesen), ebből {missing_days_count} nap kitöltve éves átlaggal ({yearly_avg_value:.4f} kWh).")
                            else:
                                st.info(f"ℹ️ Májusi adatok: {len(complete_may_df)} nap, minden nap rendelkezik mért adattal.")
                        else:
                            # Ha nincs májusi adat, akkor csak a hiányzó értékeket távolítjuk el
                            daily_df = daily_df.dropna(subset=['value', 'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
                    else:
                        # Minden más esetben: hiányzó értékek eltávolítása
                        daily_df = daily_df.dropna(subset=['value', 'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
                    
                    # Ellenőrzés: van-e elég adat az ARIMA modell betanításához
                    if len(daily_df) < 10:
                        st.warning(f"⚠️ Figyelem: Csak {len(daily_df)} napi adatpont található. Az ARIMA modell betanításához legalább 10 napi adat ajánlott.")
                    
                    if len(daily_df) == 0:
                        st.error("❌ Nincs elég adat az előrejelzéshez! Kérjük, válasszon más időszakot.")
                        st.stop()
                    
                    # Előrejelzési időszak napjainak számának meghatározása
                    forecast_days = (forecast_end_date - forecast_start_date).days + 1
                    
                    # ARIMA modell betanítása és előrejelzés
                    ts = daily_df.set_index('datetime')['value']
                    exog = daily_df.set_index('datetime')[['internal_temp', 'external_temp', 'internal_humidity', 'external_humidity']]
                    
                    # SARIMAX modell betanítása
                    model = SARIMAX(ts, 
                                  exog=exog,
                                  order=(1, 1, 1),
                                  seasonal_order=(0, 0, 0, 0),
                                  enforce_stationarity=False,
                                  enforce_invertibility=False)
                    fitted_model = model.fit()
                    
                    # Előrejelzési dátumok generálása
                    forecast_dates = pd.date_range(
                        start=forecast_start_date,
                        end=forecast_end_date,
                        freq='D'
                    )
                    
                    # Külső változók előrejelzése az előrejelzési időszakra
                    # Használjuk a történeti adatok átlagát vagy az utolsó értékeket
                    if len(exog) >= forecast_days:
                        # Ha van elég adat, az utolsó N napot használjuk
                        exog_forecast_values = exog.iloc[-forecast_days:].values
                    else:
                        # Ha nincs elég adat, az utolsó értékeket ismételjük
                        last_exog = exog.iloc[-1:].values
                        exog_forecast_values = np.tile(last_exog, (forecast_days, 1))
                    
                    # DataFrame létrehozása a megfelelő indexszel
                    exog_forecast = pd.DataFrame(
                        exog_forecast_values,
                        columns=exog.columns,
                        index=forecast_dates
                    )
                    
                    # Előrejelzés generálása
                    forecast = fitted_model.forecast(steps=forecast_days, exog=exog_forecast)
                    conf_int = fitted_model.get_forecast(steps=forecast_days, exog=exog_forecast).conf_int(alpha=0.05)
                    
                    # Előrejelzési DataFrame
                    forecast_df = pd.DataFrame({
                        'datetime': forecast_dates,
                        'forecast': forecast.values,
                        'lower_bound': conf_int.iloc[:, 0],
                        'upper_bound': conf_int.iloc[:, 1]
                    })
                    
                    # Alsó határ korlátozása 0-ra
                    forecast_df['lower_bound'] = forecast_df['lower_bound'].clip(lower=0)
                    
                    # Session state-be mentés
                    st.session_state.forecast_df = forecast_df.copy()
                    st.session_state.forecast_type = forecast_type
                    st.session_state.forecast_period = selected_period
                    
                    # Májusi adatok mentése, ha májusi adatok vannak a lekérdezésben
                    if has_may_data:
                        # Májusi napi átlagolt adatok kinyerése és mentése
                        may_data_for_display = daily_df[daily_df['datetime'].dt.month == 5].copy()
                        if len(may_data_for_display) > 0:
                            st.session_state.may_consumption_data = may_data_for_display
                    
                    st.success(f"✅ Előrejelzés sikeresen generálva {forecast_days} napra!")
                    
                else:
                    st.warning("Nincs adat a kiválasztott időszakhoz az adatbázisban!")
                    
            except Exception as e:
                st.error(f"Hiba az előrejelzés generálásakor: {e}")
                import traceback
                st.error(traceback.format_exc())
    
    # Előrejelzés megjelenítése
    if 'forecast_df' in st.session_state and st.session_state.forecast_df is not None:
        st.write("---")
        st.write("## Fogyasztás előrejelzés")
        
        try:
            forecast_df = st.session_state.forecast_df.copy()
            forecast_type = st.session_state.get('forecast_type', 'havi')
            
            # Vizuális megjelenítés - CSAK az előrejelzett időszak
            # Az előrejelzés már kWh-ban van (napi fogyasztás)
            forecast_values_for_chart = forecast_df['forecast'].copy()
            upper_bound_for_chart = forecast_df['upper_bound'].copy()
            lower_bound_for_chart = forecast_df['lower_bound'].copy()
            
            fig = go.Figure()
            
            # Előrejelzés vonal
            fig.add_trace(go.Scatter(
                x=forecast_df['datetime'],
                y=forecast_values_for_chart,
                mode='lines+markers',
                name='Előrejelzett fogyasztás',
                line=dict(color='red', width=2),
                marker=dict(size=4, symbol='circle')
            ))
            
            # Konfidencia intervallum
            fig.add_trace(go.Scatter(
                x=forecast_df['datetime'],
                y=upper_bound_for_chart,
                mode='lines',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            ))
            
            fig.add_trace(go.Scatter(
                x=forecast_df['datetime'],
                y=lower_bound_for_chart,
                mode='lines',
                line=dict(width=0),
                fill='tonexty',
                fillcolor='rgba(255,0,0,0.1)',
                name='95% konfidencia intervallum',
                hoverinfo='skip'
            ))
            
            # Diagram cím meghatározása az előrejelzés típusa alapján
            if forecast_type == "havi":
                title_suffix = "havi előrejelzés"
            elif forecast_type == "negyedéves":
                title_suffix = "negyedéves előrejelzés"
            elif forecast_type == "féléves":
                title_suffix = "féléves előrejelzés"
            else:
                title_suffix = "éves előrejelzés"
            
            fig.update_layout(
                title=f"Fogyasztás előrejelzés - {title_suffix}",
                xaxis_title="Dátum",
                yaxis_title="Napi fogyasztás (kWh)",
                hovermode='x unified',
                template="plotly_white",
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Előrejelzési értékek (már kWh-ban vannak)
            forecast_values_kwh = forecast_df['forecast'].copy()
            
            # Ár előrejelzés és költség számítás
            # 2025-ös veszteségi energiaár használata
            loss_prices = st.session_state.get('loss_prices', None)
            if loss_prices:
                try:
                    # 2025-ös ár kinyerése
                    price_2025_str = loss_prices.get('2025', '')
                    loss_price_2025 = float(price_2025_str.replace(',', '.').replace(' Ft/kWh', '')) if price_2025_str else None
                except:
                    loss_price_2025 = None
            else:
                loss_price_2025 = None
            
            if loss_price_2025 is not None:
                st.write("---")
                st.write("## Ár előrejelzés és költség számítás")
                
                daily_loss_costs = []
                
                for consumption_kwh in forecast_values_kwh:
                    # Költség: energia (kWh) × ár (Ft/kWh)
                    daily_cost = consumption_kwh * loss_price_2025
                    daily_loss_costs.append(daily_cost)
                
                # Költség statisztikák
                col1, col2, col3 = st.columns(3)
                with col1:
                    total_cost = sum(daily_loss_costs)
                    st.metric("Teljes előrejelzési időszak költség", f"{total_cost:.2f} Ft")
                with col2:
                    avg_daily_cost = total_cost / len(daily_loss_costs)
                    st.metric("Átlagos napi költség", f"{avg_daily_cost:.2f} Ft")
                with col3:
                    if forecast_type == "havi":
                        monthly_cost = total_cost
                        st.metric("Havi költség", f"{monthly_cost:.2f} Ft")
                    elif forecast_type == "negyedéves":
                        quarterly_cost = total_cost
                        st.metric("Negyedéves költség", f"{quarterly_cost:.2f} Ft")
                    elif forecast_type == "féléves":
                        semester_cost = total_cost
                        st.metric("Féléves költség", f"{semester_cost:.2f} Ft")
                    else:
                        yearly_cost = total_cost
                        st.metric("Éves költség", f"{yearly_cost:.2f} Ft")
                
                # Költség vizualizáció
                st.write("### Költség vizualizáció")
                
                fig_savings = go.Figure()
                
                fig_savings.add_trace(go.Scatter(
                    x=forecast_df['datetime'],
                    y=daily_loss_costs,
                    mode='lines+markers',
                    name='Veszteségi ár költség',
                    line=dict(color='red', width=2),
                    marker=dict(size=4)
                ))
                
                fig_savings.update_layout(
                    xaxis_title="Dátum",
                    yaxis_title="Költség (Ft)",
                    hovermode='x unified',
                    template="plotly_white",
                    height=500,
                    title="Előrejelzett energia költségek"
                )
                
                st.plotly_chart(fig_savings, use_container_width=True)
                
            else:
                st.warning("⚠️ Az ár előrejelzéshez először lekérni kell az E.ON árakat!")
                
        except Exception as e:
            st.error(f"Hiba az előrejelzés megjelenítésekor: {e}")
            import traceback
            st.error(traceback.format_exc())
    
    
