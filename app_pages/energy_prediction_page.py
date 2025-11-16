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
    if 'loss_price' in st.session_state and st.session_state.loss_price is not None:
        st.success("✅ Elérhető árak naprakészek")
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
    
    #Tábla kiválasztása
    st.write("## Adatok kiválasztása")
    
    col1, col2 = st.columns(2)
    
    with col1:
        table_options = {
            "dfv_smart_db": "Dinamikus fűtésvezérlő",
            "dfv_termosztat_db": "Termosztátos vezérlő"
        }
        
        selected_table = st.selectbox(
            "Válassz táblát:",
            options=list(table_options.keys()),
            format_func=lambda x: table_options[x],
            key="arima_table_selector"
        )
    
    

    st.write("### Időintervallum beállítása")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Kezdő dátum
        start_date = st.date_input(
            "Kezdő dátum:",
            value=datetime(2024, 8, 19),
            key="arima_start_date"
        )
    
    with col2:
        # Befejező dátum
        end_date = st.date_input(
            "Befejező dátum:",
            value=datetime(2025, 8, 21),
            key="arima_end_date"
        )
    
    # Adatok betöltése
    if st.button("Adatok betöltése", type="primary"):
        with st.spinner("Adatok betöltése folyamatban van..."):
            try:
                # Adatok lekérdezése a közvetlen teljesítmény oszlopból + külső változók
                from page_modules.database_queries import get_energy_prediction_data
                query = get_energy_prediction_data(
                    selected_table,
                    str(start_date),
                    str(end_date)
                )
                
                data = execute_query(query)
                
                if data and len(data) > 0:
                    # DataFrame létrehozása a közvetlen teljesítmény értékekkel + külső változók
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
                    
                    # Napi átlagolás az ARIMA modellhez + külső változók
                    df['date'] = df['datetime'].dt.date
                    daily_df = df.groupby('date').agg({
                        'value': 'mean',
                        'internal_temp': 'mean',
                        'external_temp': 'mean',
                        'internal_humidity': 'mean',
                        'external_humidity': 'mean'
                    }).reset_index()
                    daily_df['datetime'] = pd.to_datetime(daily_df['date'])
                    daily_df = daily_df.drop('date', axis=1)
                    daily_df = daily_df.sort_values('datetime').reset_index(drop=True)
                    
                    # Session state-be mentés (napi átlagolt adatok)
                    st.session_state.arima_data = daily_df
                    st.session_state.arima_model_trained = False
                    
                    st.success(f"✅ {len(df)} fogyasztási adatpont betöltve és {len(daily_df)} napi átlagra konvertálva!")
                    
                    # Napi átlagolt számított fogyasztás statisztikák megjelenítése
                    st.write("### Napi átlagolt számított fogyasztás statisztikák")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Napi átlagok száma", len(daily_df))
                    with col2:
                        st.metric("Minimális napi átlag", f"{daily_df['value'].min():.2f} W")
                    with col3:
                        st.metric("Maximális napi átlag", f"{daily_df['value'].max():.2f} W")
                    with col4:
                        st.metric("Átlagos napi fogyasztás", f"{daily_df['value'].mean():.2f} W")
                    
                        
                else:
                    st.warning("Nincs adat a kiválasztott időintervallumban!")
                    
            except Exception as e:
                st.error(f"Hiba az adatok betöltésekor: {e}")
    
    # ARIMA modell paraméterek beállítása
    if st.session_state.arima_data is not None and not st.session_state.arima_data.empty:
        st.write("---")
        st.write("## Fogyasztás előrejelzés")
        
        # Előrejelzési napok száma beállítása
        forecast_periods = st.number_input("Előrejelzési napok száma", min_value=1, max_value=365, value=30, step=1, key="forecast_periods")
        
        # Konfidencia szint rögzítve 95%-ra
        confidence_level = 0.95
        
        
        with st.spinner("ARIMA modell betanítása és előrejelzés generálása..."):
            try:
                df = st.session_state.arima_data.copy()
                
                # Idősor előkészítése + külső változók
                ts = df.set_index('datetime')['value']
                exog = df.set_index('datetime')[['internal_temp', 'external_temp', 'internal_humidity', 'external_humidity']]
                
                # SARIMAX modell betanítása külső változókkal (alapértelmezett paraméterek)
                model = SARIMAX(ts, 
                              exog=exog,
                              order=(1, 1, 1),  # Alapértelmezett ARIMA paraméterek
                              seasonal_order=(0, 0, 0, 0),  # Nincs szezonális komponens
                              enforce_stationarity=False,
                              enforce_invertibility=False)
                fitted_model = model.fit()
                
                # Előrejelzés külső változókkal
                forecast = fitted_model.forecast(steps=forecast_periods, exog=exog.iloc[-forecast_periods:])
                conf_int = fitted_model.get_forecast(steps=forecast_periods, exog=exog.iloc[-forecast_periods:]).conf_int(alpha=1-confidence_level)
                
                # Előrejelzési dátumok generálása (napi szinten)
                last_date = df['datetime'].max()
                forecast_dates = pd.date_range(
                    start=last_date + timedelta(days=1), 
                    periods=forecast_periods, 
                    freq='D'
                )
                
                # Előrejelzési DataFrame
                forecast_df = pd.DataFrame({
                    'datetime': forecast_dates,
                    'forecast': forecast,
                    'lower_bound': conf_int.iloc[:, 0],
                    'upper_bound': conf_int.iloc[:, 1]
                })
                
                # Alsó határ korlátozása 0-ra (fogyasztás nem lehet negatív)
                forecast_df['lower_bound'] = forecast_df['lower_bound'].clip(lower=0)
                
                # Session state-be mentés
                st.session_state.forecast_df = forecast_df.copy()
                
                # Vizuális megjelenítés
                fig = go.Figure()
                
                # Történeti napi átlagolt számított fogyasztási adatok
                fig.add_trace(go.Scatter(
                    x=df['datetime'],
                    y=df['value'],
                    mode='lines+markers',
                    name='Történeti napi átlagolt számított fogyasztás',
                    line=dict(color='blue', width=2),
                    marker=dict(size=4)
                ))
                
                # Napi számított fogyasztás előrejelzés
                fig.add_trace(go.Scatter(
                    x=forecast_df['datetime'],
                    y=forecast_df['forecast'],
                    mode='lines+markers',
                    name='Napi számított fogyasztás előrejelzés',
                    line=dict(color='red', width=2, dash='dash'),
                    marker=dict(size=4, symbol='diamond')
                ))
                
                # Konfidencia intervallum
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
                    xaxis_title="Dátum és idő",
                    yaxis_title="Napi átlagolt számított fogyasztás (W)",
                    hovermode='x unified',
                    template="plotly_white",
                    height=600
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Napi számított fogyasztás előrejelzési statisztikák
                st.write("### Napi számított fogyasztás előrejelzési eredmények")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Előrejelzett átlagos napi fogyasztás", f"{forecast.mean():.2f} W")
                with col2:
                    st.metric("Legalacsonyabb előrejelzett napi fogyasztás", f"{forecast.min():.2f} W")
                with col3:
                    st.metric("Legmagasabb előrejelzett napi fogyasztás", f"{forecast.max():.2f} W")
                with col4:
                    st.metric("Napi fogyasztás előrejelzési szórás", f"{forecast.std():.2f} W")
                
                # További napi fogyasztás-specifikus metrikák
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    # Összes előrejelzett napi energia fogyasztás
                    total_forecast_energy = forecast.sum()
                    st.metric("Összes előrejelzett napi energia", f"{total_forecast_energy:.2f} Wh")
                with col2:
                    st.write("")  # Üres oszlop
                with col3:
                    st.write("")  # Üres oszlop
                with col4:
                    st.write("")  # Üres oszlop
                
                # Napi számított fogyasztás előrejelzési táblázat
                st.write("### Részletes napi számított fogyasztás előrejelzés")
                forecast_display = forecast_df.copy()
                forecast_display['datetime'] = forecast_display['datetime'].dt.strftime('%Y-%m-%d')
                forecast_display = forecast_display.round(2)
                
                # Oszlopnevek átnevezése napi számított fogyasztás-specifikusra
                forecast_display.columns = ['Dátum', 'Előrejelzett napi számított fogyasztás (W)', 
                                          'Alsó határ (95%)', 'Felső határ (95%)']
                
                st.dataframe(forecast_display, use_container_width=True)
                
                # Napi számított fogyasztás összefoglaló
                st.write("### Napi számított fogyasztás összefoglaló")
                col1, col2 = st.columns(2)
                
                with col1:
                    last_date = df['datetime'].iloc[-1].strftime('%Y-%m-%d')
                    st.write(f"**Napi átlagolt számított fogyasztás ({last_date}):**")
                    last_consumption = df['value'].iloc[-1]
                    st.metric("Aktuális napi átlag", f"{last_consumption:.2f} W")
                
                with col2:
                    next_date = forecast_df['datetime'].iloc[0].strftime('%Y-%m-%d')
                    st.write(f"**Előrejelzett napi számított fogyasztás ({next_date}):**")
                    next_forecast = forecast.iloc[0]
                    st.metric("Következő napi előrejelzés", f"{next_forecast:.2f} W")
                
                # Ár előrejelzés és költség számítás
                if 'loss_price' in st.session_state and st.session_state.loss_price is not None:
                    st.write("---")
                    st.write("## Ár előrejelzés és költség számítás")
                    
                    # Ár előrejelzés a fogyasztás alapján
                    st.write("### Energia költség előrejelzés")
                    
                    # Előrejelzett fogyasztás átlagos napi költségei
                    avg_forecast_consumption = forecast.mean()
                    
                    # Költség számítása
                    loss_cost, loss_price_num = calculate_energy_costs(
                        avg_forecast_consumption, 
                        st.session_state.loss_price
                    )
                    
                    if loss_cost is not None:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("Átlagos napi veszteségi költség", f"{loss_cost:.2f} Ft")
                        with col2:
                            monthly_cost = loss_cost * 30
                            st.metric("Havi költség", f"{monthly_cost:.2f} Ft")
                        
                        # Költség vizualizáció
                        st.write("### Költség vizualizáció")
                        
                        # Adatok előkészítése a vizualizációhoz
                        forecast_dates_extended = pd.date_range(
                            start=df['datetime'].max() + timedelta(days=1), 
                            periods=forecast_periods, 
                            freq='D'
                        )
                        
                        # Költségek számítása minden előrejelzett napra
                        daily_loss_costs = []
                        
                        for i, consumption in enumerate(forecast):
                            loss_cost_daily, _ = calculate_energy_costs(
                                consumption, 
                                st.session_state.loss_price
                            )
                            daily_loss_costs.append(loss_cost_daily)
                        
                        # Költség grafikon
                        fig_savings = go.Figure()
                        
                        fig_savings.add_trace(go.Scatter(
                            x=forecast_dates_extended,
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
                        
                        # Összesített költség
                        total_cost = sum(daily_loss_costs)
                        st.write("### Összesített költség")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Teljes előrejelzési időszak költség", f"{total_cost:.2f} Ft")
                        with col2:
                            avg_daily_cost = total_cost / forecast_periods
                            st.metric("Átlagos napi költség", f"{avg_daily_cost:.2f} Ft")
                        with col3:
                            yearly_cost = avg_daily_cost * 365
                            st.metric("Becsült éves költség", f"{yearly_cost:.2f} Ft")
                        
                    else:
                        st.error("Nem sikerült kiszámítani a költségeket. Ellenőrizze az E.ON árak formátumát.")
                else:
                    st.warning("⚠️ Az ár előrejelzéshez először lekérni kell az E.ON árakat!")
                
            except Exception as e:
                st.error(f"Hiba az előrejelzés generálásakor: {e}")
    
    
