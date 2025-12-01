import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False

from app_services.database import execute_query
from page_modules.database_queries import get_energy_prediction_data

FORECAST_YEAR = 2026
TIME_INTERVAL_HOURS = 0.25


"CSS fájl betöltése."
def _load_css():
    try:
        with open('styles.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


"E.ON árak státusz megjelenítése."
def _display_eon_status():
    if 'loss_prices' in st.session_state and st.session_state.loss_prices is not None:
        st.success("✅ Elérhető árak naprakészek")
    elif 'eon_error' in st.session_state and st.session_state.eon_error:
        st.error(f"❌ E.ON árak lekérése sikertelen: {st.session_state.eon_error}")
    else:
        st.warning("⚠️ E.ON árak nem érhetők el")


"Session state inicializálása."
def _initialize_session_state():
    if "arima_model_trained" not in st.session_state:
        st.session_state.arima_model_trained = False
    if "arima_model" not in st.session_state:
        st.session_state.arima_model = None
    if "arima_data" not in st.session_state:
        st.session_state.arima_data = None


"Havi előrejelzés dátumainak meghatározása."
def _get_monthly_forecast_dates(selected_month):
    forecast_start_date = datetime(FORECAST_YEAR, selected_month, 1)
    if selected_month == 12:
        forecast_end_date = datetime(FORECAST_YEAR, 12, 31)
    else:
        forecast_end_date = datetime(FORECAST_YEAR, selected_month + 1, 1) - timedelta(days=1)
    return forecast_start_date, forecast_end_date, f"{selected_month:02d}"


"Negyedéves előrejelzés dátumainak meghatározása."
def _get_quarterly_forecast_dates(selected_quarter):
    quarter_dates = {
        1: (datetime(FORECAST_YEAR, 1, 1), datetime(FORECAST_YEAR, 3, 31)),
        2: (datetime(FORECAST_YEAR, 4, 1), datetime(FORECAST_YEAR, 6, 30)),
        3: (datetime(FORECAST_YEAR, 7, 1), datetime(FORECAST_YEAR, 9, 30)),
        4: (datetime(FORECAST_YEAR, 10, 1), datetime(FORECAST_YEAR, 12, 31))
    }
    forecast_start_date, forecast_end_date = quarter_dates[selected_quarter]
    return forecast_start_date, forecast_end_date, f"Q{selected_quarter}"


"Féléves előrejelzés dátumainak meghatározása."
def _get_semester_forecast_dates(selected_semester):
    if selected_semester == 1:
        forecast_start_date = datetime(FORECAST_YEAR, 1, 1)
        forecast_end_date = datetime(FORECAST_YEAR, 6, 30)
    else:
        forecast_start_date = datetime(FORECAST_YEAR, 7, 1)
        forecast_end_date = datetime(FORECAST_YEAR, 12, 31)
    return forecast_start_date, forecast_end_date, f"S{selected_semester}"


"Előrejelzési időszak kiválasztása."
def _select_forecast_period(forecast_type):
    if forecast_type == "havi":
        month_names = ["Január", "Február", "Március", "Április", "Május", "Június",
                      "Július", "Augusztus", "Szeptember", "Október", "November", "December"]
        selected_month_name = st.selectbox("Válassz hónapot:", options=month_names, key="month_selector")
        selected_month = month_names.index(selected_month_name) + 1
        st.session_state.selected_month = selected_month
        return _get_monthly_forecast_dates(selected_month)
    
    elif forecast_type == "negyedéves":
        quarter_names = [
            "1. negyedév (Január-Március)",
            "2. negyedév (Április-Június)",
            "3. negyedév (Július-Szeptember)",
            "4. negyedév (Október-December)"
        ]
        selected_quarter_name = st.selectbox("Válassz negyedévet:", options=quarter_names, key="quarter_selector")
        selected_quarter = quarter_names.index(selected_quarter_name) + 1
        st.session_state.selected_quarter = selected_quarter
        return _get_quarterly_forecast_dates(selected_quarter)
    
    elif forecast_type == "féléves":
        semester_names = ["1. félév (Január-Június)", "2. félév (Július-December)"]
        selected_semester_name = st.selectbox("Válassz félévet:", options=semester_names, key="semester_selector")
        selected_semester = semester_names.index(selected_semester_name) + 1
        st.session_state.selected_semester = selected_semester
        return _get_semester_forecast_dates(selected_semester)
    
    else:
        return datetime(FORECAST_YEAR, 1, 1), datetime(FORECAST_YEAR, 12, 31), "2026"


"Havi adatok lekérdezése."
def _query_monthly_data(selected_table, selected_month_value, power_column, current_column, 
                       temp_column, humidity_column):
    if selected_month_value == 5:
        query = f"""
        SELECT date, time, 
               {power_column} as value,
               {current_column} as current,
               {temp_column} as internal_temp,
               trend_kulso_homerseklet_pillanatnyi as external_temp,
               {humidity_column} as internal_humidity,
               trend_kulso_paratartalom as external_humidity
        FROM {selected_table}
        WHERE DATE(date) BETWEEN '2025-05-01' AND '2025-05-31'
        AND {power_column} IS NOT NULL 
        AND {current_column} IS NOT NULL
        AND {temp_column} IS NOT NULL
        AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
        ORDER BY date, time
        """
    else:
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
    return execute_query(query)


"Negyedéves adatok lekérdezése."
def _query_quarterly_data(selected_table, selected_quarter, power_column, current_column,
                          temp_column, humidity_column):
    quarter_months = {
        1: [1, 2, 3],
        2: [4, 5, 6],
        3: [7, 8, 9],
        4: [10, 11, 12]
    }
    month_list = ','.join(map(str, quarter_months[selected_quarter]))
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
    return execute_query(query)


"Féléves adatok lekérdezése."
def _query_semester_data(selected_table, selected_semester, power_column, current_column,
                        temp_column, humidity_column):
    semester_months = {
        1: [1, 2, 3, 4, 5, 6],
        2: [7, 8, 9, 10, 11, 12]
    }
    month_list = ','.join(map(str, semester_months[selected_semester]))
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
    return execute_query(query)


"Történeti adatok lekérdezése."
def _fetch_historical_data(forecast_type, selected_table):
    power_column = "trend_smart_p" if selected_table == "dfv_smart_db" else "trend_termosztat_p"
    current_column = "trend_smart_i1" if selected_table == "dfv_smart_db" else "trend_termosztat_i1"
    temp_column = "trend_smart_t" if selected_table == "dfv_smart_db" else "trend_termosztat_t"
    humidity_column = "trend_smart_rh" if selected_table == "dfv_smart_db" else "trend_termosztat_rh"
    
    if forecast_type == "havi":
        if 'selected_month' not in st.session_state:
            st.error("Hiba: Kérjük, válasszon hónapot az előrejelzéshez!")
            st.stop()
        return _query_monthly_data(selected_table, st.session_state.selected_month,
                                  power_column, current_column, temp_column, humidity_column)
    
    elif forecast_type == "negyedéves":
        if 'selected_quarter' not in st.session_state:
            st.error("Hiba: Kérjük, válasszon negyedévet az előrejelzéshez!")
            st.stop()
        return _query_quarterly_data(selected_table, st.session_state.selected_quarter,
                                    power_column, current_column, temp_column, humidity_column)
    
    elif forecast_type == "féléves":
        if 'selected_semester' not in st.session_state:
            st.error("Hiba: Kérjük, válasszon félévet az előrejelzéshez!")
            st.stop()
        return _query_semester_data(selected_table, st.session_state.selected_semester,
                                   power_column, current_column, temp_column, humidity_column)
    
    else:
        query = get_energy_prediction_data(selected_table, "2024-01-01", "2025-12-31")
        return execute_query(query)


"DataFrame előkészítése."
def _prepare_dataframe(data):
    df = pd.DataFrame(data, columns=['date', 'time', 'value', 'current', 
                                     'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
    
    for col in ['value', 'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['value'])
    df = df.sort_values('datetime').reset_index(drop=True)
    return df


"Éves átlagok számítása."
def _calculate_yearly_averages(selected_table):
    query = get_energy_prediction_data(selected_table, "2024-01-01", "2025-12-31")
    yearly_data = execute_query(query)
    
    if not yearly_data or len(yearly_data) == 0:
        return None, None, None, None, None
    
    yearly_df = pd.DataFrame(yearly_data, columns=['date', 'time', 'value', 'current', 
                                                    'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
    for col in ['value', 'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity']:
        yearly_df[col] = pd.to_numeric(yearly_df[col], errors='coerce')
    yearly_df = yearly_df.dropna(subset=['value'])
    
    yearly_df['datetime'] = pd.to_datetime(yearly_df['date'].astype(str) + ' ' + yearly_df['time'].astype(str))
    yearly_df['date'] = yearly_df['datetime'].dt.date
    
    yearly_daily_consumption = yearly_df.groupby('date')['value'].sum() * TIME_INTERVAL_HOURS
    yearly_avg_value = yearly_daily_consumption.mean()
    yearly_avg_internal_temp = yearly_df.groupby('date')['internal_temp'].mean().mean()
    yearly_avg_external_temp = yearly_df.groupby('date')['external_temp'].mean().mean()
    yearly_avg_internal_humidity = yearly_df.groupby('date')['internal_humidity'].mean().mean()
    yearly_avg_external_humidity = yearly_df.groupby('date')['external_humidity'].mean().mean()
    
    return yearly_avg_value, yearly_avg_internal_temp, yearly_avg_external_temp, \
           yearly_avg_internal_humidity, yearly_avg_external_humidity


"Ellenőrzi, hogy van-e májusi adat."
def _check_has_may_data(forecast_type):
    if forecast_type == "havi" and st.session_state.get('selected_month') == 5:
        return True
    elif forecast_type == "negyedéves" and st.session_state.get('selected_quarter') == 2:
        return True
    elif forecast_type == "féléves" and st.session_state.get('selected_semester') == 1:
        return True
    elif forecast_type == "éves":
        return True
    return False


"Májusi hiányzó napok kitöltése éves átlaggal."
def _fill_may_data(daily_df, yearly_avg_value, yearly_avg_internal_temp, 
                   yearly_avg_external_temp, yearly_avg_internal_humidity, 
                   yearly_avg_external_humidity, forecast_type):
    may_start = datetime(2025, 5, 1)
    may_end = datetime(2025, 5, 31)
    all_may_dates = pd.date_range(start=may_start, end=may_end, freq='D')
    may_dates_in_data = daily_df[daily_df['datetime'].dt.month == 5]
    
    if len(may_dates_in_data) > 0 or forecast_type == "havi":
        complete_may_df = pd.DataFrame({'datetime': all_may_dates})
        may_data_from_daily = daily_df[daily_df['datetime'].dt.month == 5][
            ['datetime', 'value', 'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity']
        ]
        complete_may_df = complete_may_df.merge(may_data_from_daily, on='datetime', how='left')
        missing_days_count = complete_may_df['value'].isna().sum()
        
        complete_may_df['value'] = complete_may_df['value'].fillna(yearly_avg_value)
        complete_may_df['internal_temp'] = complete_may_df['internal_temp'].fillna(yearly_avg_internal_temp)
        complete_may_df['external_temp'] = complete_may_df['external_temp'].fillna(yearly_avg_external_temp)
        complete_may_df['internal_humidity'] = complete_may_df['internal_humidity'].fillna(yearly_avg_internal_humidity)
        complete_may_df['external_humidity'] = complete_may_df['external_humidity'].fillna(yearly_avg_external_humidity)
        
        complete_may_df = complete_may_df.sort_values('datetime').reset_index(drop=True)
        daily_df_without_may = daily_df[daily_df['datetime'].dt.month != 5]
        daily_df = pd.concat([daily_df_without_may, complete_may_df], ignore_index=True)
        daily_df = daily_df.sort_values('datetime').reset_index(drop=True)
        
       
    return daily_df


"Napi DataFrame előkészítése."
def _prepare_daily_dataframe(df, has_may_data, selected_table):
    df['date'] = df['datetime'].dt.date
    daily_consumption = df.groupby('date')['value'].sum() * TIME_INTERVAL_HOURS
    
    daily_df = df.groupby('date').agg({
        'internal_temp': 'mean',
        'external_temp': 'mean',
        'internal_humidity': 'mean',
        'external_humidity': 'mean'
    }).reset_index()
    
    daily_df['value'] = daily_consumption.values
    daily_df['datetime'] = pd.to_datetime(daily_df['date'])
    daily_df = daily_df.drop('date', axis=1)
    daily_df = daily_df.sort_values('datetime').reset_index(drop=True)
    
    if has_may_data:
        yearly_avg_value, yearly_avg_internal_temp, yearly_avg_external_temp, \
        yearly_avg_internal_humidity, yearly_avg_external_humidity = _calculate_yearly_averages(selected_table)
        
        if yearly_avg_value is not None:
            daily_df = _fill_may_data(daily_df, yearly_avg_value, yearly_avg_internal_temp,
                                     yearly_avg_external_temp, yearly_avg_internal_humidity,
                                     yearly_avg_external_humidity, "havi" if has_may_data else None)
        else:
            daily_df = daily_df.dropna(subset=['value', 'internal_temp', 'external_temp', 
                                               'internal_humidity', 'external_humidity'])
    else:
        daily_df = daily_df.dropna(subset=['value', 'internal_temp', 'external_temp', 
                                           'internal_humidity', 'external_humidity'])
    
    return daily_df


"ARIMA modell betanítása és előrejelzés."
def _train_arima_model(daily_df, forecast_days, forecast_start_date, forecast_end_date):
    ts = daily_df.set_index('datetime')['value']
    exog = daily_df.set_index('datetime')[['internal_temp', 'external_temp', 'internal_humidity', 'external_humidity']]
    
    model = SARIMAX(ts, exog=exog, order=(1, 1, 1), seasonal_order=(0, 0, 0, 0),
                   enforce_stationarity=False, enforce_invertibility=False)
    fitted_model = model.fit()
    
    forecast_dates = pd.date_range(start=forecast_start_date, end=forecast_end_date, freq='D')
    
    if len(exog) >= forecast_days:
        exog_forecast_values = exog.iloc[-forecast_days:].values
    else:
        last_exog = exog.iloc[-1:].values
        exog_forecast_values = np.tile(last_exog, (forecast_days, 1))
    
    exog_forecast = pd.DataFrame(exog_forecast_values, columns=exog.columns, index=forecast_dates)
    forecast = fitted_model.forecast(steps=forecast_days, exog=exog_forecast)
    conf_int = fitted_model.get_forecast(steps=forecast_days, exog=exog_forecast).conf_int(alpha=0.05)
    
    forecast_df = pd.DataFrame({
        'datetime': forecast_dates,
        'forecast': forecast.values,
        'lower_bound': conf_int.iloc[:, 0],
        'upper_bound': conf_int.iloc[:, 1]
    })
    forecast_df['lower_bound'] = forecast_df['lower_bound'].clip(lower=0)
    
    return forecast_df


"Előrejelzés diagram létrehozása."
def _create_forecast_chart(forecast_df, forecast_type):
    title_suffixes = {
        "havi": "havi előrejelzés",
        "negyedéves": "negyedéves előrejelzés",
        "féléves": "féléves előrejelzés",
        "éves": "éves előrejelzés"
    }
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=forecast_df['datetime'],
        y=forecast_df['forecast'],
        mode='lines+markers',
        name='Előrejelzett fogyasztás',
        line=dict(color='red', width=2),
        marker=dict(size=4, symbol='circle')
    ))
    fig.add_trace(go.Scatter(
        x=forecast_df['datetime'],
        y=forecast_df['upper_bound'],
        mode='lines',
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=forecast_df['datetime'],
        y=forecast_df['lower_bound'],
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor='rgba(255,0,0,0.1)',
        name='95% konfidencia intervallum',
        hoverinfo='skip'
    ))
    
    fig.update_layout(
        title=f"Fogyasztás előrejelzés - {title_suffixes.get(forecast_type, 'előrejelzés')}",
        xaxis_title="Dátum",
        yaxis_title="Napi fogyasztás (kWh)",
        hovermode='x unified',
        template="plotly_white",
        height=600
    )
    
    return fig


"2025-ös veszteségi ár feldolgozása."
def _parse_loss_price_2025():
    loss_prices = st.session_state.get('loss_prices', None)
    if not loss_prices:
        return None
    
    try:
        price_2025_str = loss_prices.get('2025', '')
        return float(price_2025_str.replace(',', '.').replace(' Ft/kWh', '')) if price_2025_str else None
    except:
        return None


"Költség metrikák megjelenítése."
def _display_cost_metrics(forecast_df, forecast_type, loss_price_2025):
    forecast_values_kwh = forecast_df['forecast'].copy()
    daily_loss_costs = [consumption_kwh * loss_price_2025 for consumption_kwh in forecast_values_kwh]
    total_cost = sum(daily_loss_costs)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Teljes előrejelzési időszak költség", f"{total_cost:.2f} Ft")
    with col2:
        st.metric("Átlagos napi költség", f"{total_cost / len(daily_loss_costs):.2f} Ft")
    with col3:
        cost_labels = {
            "havi": "Havi költség",
            "negyedéves": "Negyedéves költség",
            "féléves": "Féléves költség",
            "éves": "Éves költség"
        }
        st.metric(cost_labels.get(forecast_type, "Költség"), f"{total_cost:.2f} Ft")
    
    return daily_loss_costs


"Költség diagram létrehozása."
def _create_cost_chart(forecast_df, daily_loss_costs):
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
    return fig_savings


"Előrejelzés generálása."
def _generate_forecast(selected_table, forecast_type, forecast_start_date, forecast_end_date, selected_period):
    data = _fetch_historical_data(forecast_type, selected_table)
    
    if not data or len(data) == 0:
        st.warning("Nincs adat a kiválasztott időszakhoz az adatbázisban!")
        return
    
    df = _prepare_dataframe(data)
    has_may_data = _check_has_may_data(forecast_type)
    daily_df = _prepare_daily_dataframe(df, has_may_data, selected_table)
    
    if len(daily_df) < 10:
        st.warning(f"⚠️ Figyelem: Csak {len(daily_df)} napi adatpont található. Az ARIMA modell betanításához legalább 10 napi adat ajánlott.")
    
    if len(daily_df) == 0:
        st.error("❌ Nincs elég adat az előrejelzéshez! Kérjük, válasszon más időszakot.")
        return
    
    forecast_days = (forecast_end_date - forecast_start_date).days + 1
    forecast_df = _train_arima_model(daily_df, forecast_days, forecast_start_date, forecast_end_date)
    
    st.session_state.forecast_df = forecast_df.copy()
    st.session_state.forecast_type = forecast_type
    st.session_state.forecast_period = selected_period
    
    if has_may_data:
        may_data_for_display = daily_df[daily_df['datetime'].dt.month == 5].copy()
        if len(may_data_for_display) > 0:
            st.session_state.may_consumption_data = may_data_for_display
    
    st.success(f"✅ Előrejelzés sikeresen generálva {forecast_days} napra!")


"Előrejelzés eredmények megjelenítése."
def _display_forecast_results():
    forecast_df = st.session_state.forecast_df.copy()
    forecast_type = st.session_state.get('forecast_type', 'havi')
    
    fig = _create_forecast_chart(forecast_df, forecast_type)
    st.plotly_chart(fig, use_container_width=True)
    
    loss_price_2025 = _parse_loss_price_2025()
    
    if loss_price_2025 is not None:
        st.write("---")
        st.write("## Ár előrejelzés és költség számítás")
        daily_loss_costs = _display_cost_metrics(forecast_df, forecast_type, loss_price_2025)
        st.write("### Költség vizualizáció")
        fig_savings = _create_cost_chart(forecast_df, daily_loss_costs)
        st.plotly_chart(fig_savings, use_container_width=True)
    else:
        st.warning("⚠️ Az ár előrejelzéshez először lekérni kell az E.ON árakat!")


"Energiafogyasztás és megtakarítás előrejelzés oldal."
def show_energy_prediction_page():
    _load_css()
    st.write("# Energiafogyasztás és megtakarítás előrejelzés")
    
    _display_eon_status()
    st.write("---")
    _initialize_session_state()
    
    selected_table = "dfv_smart_db"
    
    st.write("---")
    st.write("## Előrejelzés típusa")
    
    forecast_type = st.selectbox(
        "Válassz előrejelzési típust:",
        options=["havi", "negyedéves", "féléves", "éves"],
        key="forecast_type_selector"
    )
    
    forecast_start_date, forecast_end_date, selected_period = _select_forecast_period(forecast_type)
    
    if st.button("Előrejelzés generálása", type="primary"):
        with st.spinner("Adatok betöltése és előrejelzés generálása folyamatban..."):
            try:
                _generate_forecast(selected_table, forecast_type, forecast_start_date, 
                                 forecast_end_date, selected_period)
            except Exception as e:
                st.error(f"Hiba az előrejelzés generálásakor: {e}")
                import traceback
                st.error(traceback.format_exc())
    
    if 'forecast_df' in st.session_state and st.session_state.forecast_df is not None:
        st.write("---")
        st.write("## Fogyasztás előrejelzés")
        try:
            _display_forecast_results()
        except Exception as e:
            st.error(f"Hiba az előrejelzés megjelenítésekor: {e}")
            import traceback
            st.error(traceback.format_exc())
