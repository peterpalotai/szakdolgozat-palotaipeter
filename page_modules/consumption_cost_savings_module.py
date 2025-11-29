import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_services.database import execute_query
from page_modules.database_queries import get_smart_controller_data, get_thermostat_controller_data

TIME_INTERVAL_HOURS = 0.25
HEATER_USAGE_HOURS = 24
MAX_PAYBACK_MONTHS = 1000

"""Veszteségi árak feldolgozása. Ha nincs cache-elve akkor visszaadja a None értéket."""
def _parse_loss_prices():
    loss_prices = st.session_state.get('loss_prices', None)
    if not loss_prices:
        return None, None
    
    try:
        price_2024_str = loss_prices.get('2024', '')
        price_2025_str = loss_prices.get('2025', '')
        loss_price_2024 = float(price_2024_str.replace(',', '.').replace(' Ft/kWh', '')) if price_2024_str else None
        loss_price_2025 = float(price_2025_str.replace(',', '.').replace(' Ft/kWh', '')) if price_2025_str else None
        return loss_price_2024, loss_price_2025
    except:
        return None, None

"""DataFrame-ek előkészítése."""
def _prepare_dataframes(smart_data, thermostat_data):
    smart_df = pd.DataFrame(smart_data, columns=['date', 'time', 'value', 'current', 
                                                 'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
    thermostat_df = pd.DataFrame(thermostat_data, columns=['date', 'time', 'value', 'current', 
                                                          'internal_temp', 'external_temp', 'internal_humidity', 'external_humidity'])
    
    smart_df['datetime'] = pd.to_datetime(smart_df['date'].astype(str) + ' ' + smart_df['time'].astype(str))
    thermostat_df['datetime'] = pd.to_datetime(thermostat_df['date'].astype(str) + ' ' + thermostat_df['time'].astype(str))
    
    smart_df['value'] = pd.to_numeric(smart_df['value'], errors='coerce')
    thermostat_df['value'] = pd.to_numeric(thermostat_df['value'], errors='coerce')
    
    smart_df = smart_df.dropna(subset=['value'])
    thermostat_df = thermostat_df.dropna(subset=['value'])
    
    smart_df['date'] = smart_df['datetime'].dt.date
    thermostat_df['date'] = thermostat_df['datetime'].dt.date
    
    smart_df['energy_kwh'] = smart_df['value'] * TIME_INTERVAL_HOURS
    thermostat_df['energy_kwh'] = thermostat_df['value'] * TIME_INTERVAL_HOURS
    
    return smart_df, thermostat_df

"""Napi energia számítása."""
def _calculate_daily_energy(smart_df, thermostat_df):
    smart_daily_energy_df = smart_df.groupby('date')['energy_kwh'].sum().reset_index()
    smart_daily_energy_df.columns = ['date', 'daily_energy_kwh']
    thermostat_daily_energy_df = thermostat_df.groupby('date')['energy_kwh'].sum().reset_index()
    thermostat_daily_energy_df.columns = ['date', 'daily_energy_kwh']
    
    smart_daily_energy_df['datetime'] = pd.to_datetime(smart_daily_energy_df['date'])
    thermostat_daily_energy_df['datetime'] = pd.to_datetime(thermostat_daily_energy_df['date'])
    
    return smart_daily_energy_df, thermostat_daily_energy_df


"""Működési órák számítása."""
def _calculate_operating_hours(smart_df, thermostat_df):
    smart_daily_operating_intervals = smart_df.groupby('date').apply(
        lambda x: (x['value'] > 0).sum()
    ).mean()
    thermostat_daily_operating_intervals = thermostat_df.groupby('date').apply(
        lambda x: (x['value'] > 0).sum()
    ).mean()
    
    smart_operating_hours = smart_daily_operating_intervals * TIME_INTERVAL_HOURS
    thermostat_operating_hours = thermostat_daily_operating_intervals * TIME_INTERVAL_HOURS
    
    return smart_operating_hours, thermostat_operating_hours

"""Költségek számítása dátum alapján."""
def _calculate_costs(smart_daily_energy_df, thermostat_daily_energy_df, heater_daily_energy, 
                    loss_price_2024, loss_price_2025):
    smart_daily_energy_df['year'] = pd.to_datetime(smart_daily_energy_df['date']).dt.year
    thermostat_daily_energy_df['year'] = pd.to_datetime(thermostat_daily_energy_df['date']).dt.year
    
    smart_daily_energy_df['daily_cost_ft'] = smart_daily_energy_df.apply(
        lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
        axis=1
    )
    thermostat_daily_energy_df['daily_cost_ft'] = thermostat_daily_energy_df.apply(
        lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
        axis=1
    )
    
    smart_daily_energy_df['heater_daily_cost_ft'] = smart_daily_energy_df.apply(
        lambda row: heater_daily_energy * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
        axis=1
    )
    thermostat_daily_energy_df['heater_daily_cost_ft'] = thermostat_daily_energy_df.apply(
        lambda row: heater_daily_energy * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
        axis=1
    )
    
    total_days = len(smart_daily_energy_df)
    total_smart_cost = smart_daily_energy_df['daily_cost_ft'].sum()
    total_thermostat_cost = thermostat_daily_energy_df['daily_cost_ft'].sum()
    total_heater_cost = smart_daily_energy_df['heater_daily_cost_ft'].sum()
    
    smart_loss_cost = total_smart_cost / total_days if total_days > 0 else 0
    thermostat_loss_cost = total_thermostat_cost / total_days if total_days > 0 else 0
    heater_loss_cost = total_heater_cost / total_days if total_days > 0 else 0
    
    return smart_loss_cost, thermostat_loss_cost, heater_loss_cost, total_days

"""Megtakarítás számítása a dinamikus és termosztátos vezérlők között."""
def _calculate_savings(smart_daily_energy_df, thermostat_daily_energy_df, heater_daily_energy,
                       loss_price_2024, loss_price_2025, total_days):
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
    
    total_smart_savings_cost = smart_daily_energy_df['daily_savings_cost'].sum()
    total_thermostat_savings_cost = thermostat_daily_energy_df['daily_savings_cost'].sum()
    total_smart_savings_energy = smart_daily_energy_df['daily_savings_energy'].sum()
    total_thermostat_savings_energy = thermostat_daily_energy_df['daily_savings_energy'].sum()
    
    smart_savings_cost = total_smart_savings_cost / total_days if total_days > 0 else 0
    thermostat_savings_cost = total_thermostat_savings_cost / total_days if total_days > 0 else 0
    smart_savings_energy = total_smart_savings_energy / total_days if total_days > 0 else 0
    thermostat_savings_energy = total_thermostat_savings_energy / total_days if total_days > 0 else 0
    
    return smart_savings_cost, thermostat_savings_cost, smart_savings_energy, thermostat_savings_energy

"""Dinamikus vs Termosztátos megtakarítás számítása."""
def _calculate_smart_vs_thermo_savings(smart_daily_energy_df, thermostat_daily_energy_df,
                                       loss_price_2024, loss_price_2025):
    smart_thermo_comparison = smart_daily_energy_df[['date', 'daily_energy_kwh', 'daily_cost_ft', 'year']].copy()
    smart_thermo_comparison.columns = ['date', 'smart_energy', 'smart_cost', 'year']
    thermo_comparison = thermostat_daily_energy_df[['date', 'daily_energy_kwh', 'daily_cost_ft']].copy()
    thermo_comparison.columns = ['date', 'thermo_energy', 'thermo_cost']
    smart_thermo_comparison = smart_thermo_comparison.merge(thermo_comparison, on='date', how='inner')
    
    smart_thermo_comparison['daily_savings_energy_smart_vs_thermo'] = \
        smart_thermo_comparison['thermo_energy'] - smart_thermo_comparison['smart_energy']
    smart_thermo_comparison['daily_savings_cost_smart_vs_thermo'] = smart_thermo_comparison.apply(
        lambda row: row['daily_savings_energy_smart_vs_thermo'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
        axis=1
    )
    
    comparison_days = len(smart_thermo_comparison)
    total_smart_vs_thermo_savings_energy = smart_thermo_comparison['daily_savings_energy_smart_vs_thermo'].sum()
    total_smart_vs_thermo_savings_cost = smart_thermo_comparison['daily_savings_cost_smart_vs_thermo'].sum()
    
    smart_vs_thermo_savings_energy = total_smart_vs_thermo_savings_energy / comparison_days if comparison_days > 0 else 0
    smart_vs_thermo_savings_cost = total_smart_vs_thermo_savings_cost / comparison_days if comparison_days > 0 else 0
    
    return smart_vs_thermo_savings_energy, smart_vs_thermo_savings_cost, smart_thermo_comparison

"Vezérlő táblázat oldal méret beállítása."
def _setup_controller_table_page_size():
    if "controller_table_page_size" not in st.session_state:
        st.session_state.controller_table_page_size = 5
    if "prev_controller_table_page_size" not in st.session_state:
        st.session_state.prev_controller_table_page_size = st.session_state.controller_table_page_size
    if "controller_table_offset" not in st.session_state:
        st.session_state.controller_table_offset = 0
    
    col1, col2 = st.columns([1, 2])
    with col1:
        page_size_options = [5, 15, 25]
        current_page_size = st.session_state.controller_table_page_size
        try:
            current_index = page_size_options.index(current_page_size)
        except ValueError:
            current_index = 0
        
        page_size = st.selectbox("Elemek száma:", page_size_options, index=current_index, key="controller_table_page_size_selector")
        
        if page_size != st.session_state.prev_controller_table_page_size:
            st.session_state.controller_table_offset = 0
            st.session_state.prev_controller_table_page_size = page_size
        
        st.session_state.controller_table_page_size = page_size
    with col2:
        st.write("")


"Vezérlő táblázat lapozás vezérlőelemek megjelenítése."
def _display_controller_table_pagination(total_rows):
    if "controller_table_offset" not in st.session_state:
        st.session_state.controller_table_offset = 0
    
    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 0.2, 0.2, 0.2, 0.2, 0.1, 0.3])
    
    with col1:
        st.write("")
    with col2:
        if st.button("⏮️", key="controller_table_first_page"):
            st.session_state.controller_table_offset = 0
            st.rerun()
    with col3:
        current_page_size = st.session_state.controller_table_page_size
        if st.button("⬅️", key="controller_table_prev_page"):
            if st.session_state.controller_table_offset >= current_page_size:
                st.session_state.controller_table_offset -= current_page_size
                st.rerun()
    with col4:
        current_page_size = st.session_state.controller_table_page_size
        next_offset = st.session_state.controller_table_offset + current_page_size
        has_next_page = next_offset < total_rows
        
        if st.button("➡️", disabled=not has_next_page, key="controller_table_next_page"):
            st.session_state.controller_table_offset = next_offset
            st.rerun()
    with col5:
        current_page_size = st.session_state.controller_table_page_size
        last_page_offset = ((total_rows - 1) // current_page_size) * current_page_size
        is_on_last_page = st.session_state.controller_table_offset >= last_page_offset
        
        if st.button("⏭️", disabled=is_on_last_page, key="controller_table_last_page"):
            st.session_state.controller_table_offset = last_page_offset
            st.rerun()
    with col6:
        st.write("")
    with col7:
        current_page_size = st.session_state.controller_table_page_size
        current_page = (st.session_state.controller_table_offset // current_page_size) + 1
        total_pages = (total_rows + current_page_size - 1) // current_page_size
        st.write(f" **Oldal:** {current_page} / {total_pages}")


"Vezérlő táblázat megjelenítése."
def _display_controller_table(smart_daily_energy_df, thermostat_daily_energy_df, 
                            loss_price_2024, loss_price_2025):
    if "prev_controller_choice" not in st.session_state:
        st.session_state.prev_controller_choice = None
    
    col1, col2 = st.columns([1, 3])
    with col1:
        controller_choice = st.selectbox(
            "Vezérlő kiválasztása:",
            ["Dinamikus fűtésvezérlő", "Termosztátos vezérlő"],
            key="controller_comparison_choice"
        )
    
    if controller_choice != st.session_state.prev_controller_choice:
        st.session_state.controller_table_offset = 0
        st.session_state.prev_controller_choice = controller_choice
    
    if controller_choice == "Dinamikus fűtésvezérlő":
        selected_df = smart_daily_energy_df[['date', 'daily_energy_kwh', 'year']].copy()
    else:
        selected_df = thermostat_daily_energy_df[['date', 'daily_energy_kwh', 'year']].copy()
    
    if loss_price_2024 is not None and loss_price_2025 is not None:
        selected_df['Költség (Ft)'] = selected_df.apply(
            lambda row: row['daily_energy_kwh'] * (loss_price_2024 if row['year'] == 2024 else loss_price_2025),
            axis=1
        )
    else:
        selected_df['Költség (Ft)'] = 0.0
    
    selected_df['date'] = pd.to_datetime(selected_df['date']).dt.strftime('%Y-%m-%d')
    selected_df = selected_df.sort_values('date')
    selected_df = selected_df[['date', 'daily_energy_kwh', 'Költség (Ft)']]
    selected_df.columns = ['Dátum', 'Fogyasztás (kWh)', 'Költség (Ft)']
    
    _setup_controller_table_page_size()
    
    total_rows = len(selected_df)
    current_page_size = st.session_state.controller_table_page_size
    start_idx = st.session_state.controller_table_offset
    end_idx = min(start_idx + current_page_size, total_rows)
    selected_df_paginated = selected_df.iloc[start_idx:end_idx]
    
    st.dataframe(
        selected_df_paginated,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Dátum": st.column_config.TextColumn("Dátum", width="medium"),
            "Fogyasztás (kWh)": st.column_config.NumberColumn("Fogyasztás (kWh)", format="%.2f", width="medium"),
            "Költség (Ft)": st.column_config.NumberColumn("Költség (Ft)", format="%.2f", width="medium")
        }
    )
    
    _display_controller_table_pagination(total_rows)

"""Folyamatos működés metrikák megjelenítése."""
def _display_heater_metrics(smart_daily_energy_df, heater_daily_energy, 
                            loss_price_2024, loss_price_2025):
    st.write("")
    st.write("**Folyamatos működés esetén:**")
    
    if 'year' not in smart_daily_energy_df.columns:
        smart_daily_energy_df['year'] = pd.to_datetime(smart_daily_energy_df['date']).dt.year
    
    heater_cost_2024 = smart_daily_energy_df[smart_daily_energy_df['year'] == 2024]['heater_daily_cost_ft'].mean() \
        if (smart_daily_energy_df['year'] == 2024).any() else None
    heater_cost_2025 = smart_daily_energy_df[smart_daily_energy_df['year'] == 2025]['heater_daily_cost_ft'].mean() \
        if (smart_daily_energy_df['year'] == 2025).any() else None
    
    if heater_cost_2024 is None and loss_price_2024 is not None:
        heater_cost_2024 = heater_daily_energy * loss_price_2024
    if heater_cost_2025 is None and loss_price_2025 is not None:
        heater_cost_2025 = heater_daily_energy * loss_price_2025
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Napi fogyasztás (kWh)", f"{heater_daily_energy:.2f}")
    with col2:
        st.metric("2024 - Napi veszteségi energiaár költség (Ft)", 
                 f"{heater_cost_2024:.2f}" if heater_cost_2024 is not None else "N/A")
    with col3:
        st.metric("2025 - Napi veszteségi energiaár költség (Ft)", 
                 f"{heater_cost_2025:.2f}" if heater_cost_2025 is not None else "N/A")


"""Összehasonlítás adatok meghatározása."""
def _get_comparison_data(smart_selected, thermo_selected, heater_selected,
                         smart_savings_energy, smart_savings_cost,
                         thermostat_savings_energy, thermostat_savings_cost,
                         smart_vs_thermo_savings_energy, smart_vs_thermo_savings_cost,
                         consumption_diff_smart_heater, consumption_diff_thermo_heater,
                         consumption_diff_smart_thermo):
    if smart_selected and thermo_selected:
        comparison_title = "Dinamikus fűtésvezérlő vs Termosztátos vezérlő"
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
        consumption_savings = abs(consumption_diff_smart_thermo) if consumption_diff_smart_thermo < 0 else 0
    
    elif smart_selected and heater_selected:
        comparison_title = "Dinamikus fűtésvezérlő vs Folyamatos működés esetén"
        energy_savings_energy = smart_savings_energy
        energy_savings_cost = smart_savings_cost
        note_text = None
        consumption_savings = abs(consumption_diff_smart_heater) if consumption_diff_smart_heater < 0 else 0
    
    elif thermo_selected and heater_selected:
        comparison_title = "Termosztátos vezérlő vs Folyamatos működés esetén"
        energy_savings_energy = thermostat_savings_energy
        energy_savings_cost = thermostat_savings_cost
        note_text = None
        consumption_savings = abs(consumption_diff_thermo_heater) if consumption_diff_thermo_heater < 0 else 0
    
    else:
        return None, None, None, None
    
    return comparison_title, energy_savings_energy, energy_savings_cost, note_text

"""Összehasonlítás táblázat megjelenítése."""
def _display_comparison_table(energy_savings_energy, energy_savings_cost):
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

"""Összefoglaló táblázat megjelenítése."""
def _display_summary_table(smart_daily_energy_df, thermostat_daily_energy_df, 
                          smart_thermo_comparison, heater_daily_energy,
                          yearly_diff_smart_heater, yearly_diff_thermo_heater, yearly_diff_smart_thermo):
    smart_heater_consumption_diff_total = (smart_daily_energy_df['daily_energy_kwh'] - heater_daily_energy).sum()
    thermo_heater_consumption_diff_total = (thermostat_daily_energy_df['daily_energy_kwh'] - heater_daily_energy).sum()
    smart_thermo_consumption_diff_total = (smart_thermo_comparison['smart_energy'] - smart_thermo_comparison['thermo_energy']).sum()
    
    summary_data = {
        'Összehasonlítás': [
            'Dinamikus fűtésvezérlő vs Folyamatos működés esetén',
            'Termosztátos vezérlő vs Folyamatos működés esetén',
            'Dinamikus fűtésvezérlő vs Termosztátos vezérlő'
        ],
        'Fogyasztás különbség éves szinten (kWh)': [
            f"{smart_heater_consumption_diff_total:.2f}",
            f"{thermo_heater_consumption_diff_total:.2f}",
            f"{smart_thermo_consumption_diff_total:.2f}"
        ],
        'Éves költség különbség (Ft)': [
            f"{yearly_diff_smart_heater:.2f}",
            f"{yearly_diff_thermo_heater:.2f}",
            f"{yearly_diff_smart_thermo:.2f}"
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

"""Megtérülési görbe létrehozása."""
def _create_payback_chart(payback_days, payback_months, investment_cost, daily_savings_smart_vs_thermo):
    max_days = min(int(payback_days * 1.2), 365 * 5)
    days_range = list(range(0, max_days + 1, 7))
    cumulative_savings = [daily_savings_smart_vs_thermo * day for day in days_range]
    investment_line = [investment_cost] * len(days_range)
    months_range = [day / 30 for day in days_range]
    
    fig_payback = go.Figure()
    fig_payback.add_trace(go.Scatter(
        x=months_range,
        y=cumulative_savings,
        mode='lines',
        name='Kumulatív megtakarítás',
        line=dict(color='#00CC96', width=3),
        hovertemplate='%{x:.1f} hónap<br>%{y:,.0f} Ft<extra></extra>'
    ))
    fig_payback.add_trace(go.Scatter(
        x=months_range,
        y=investment_line,
        mode='lines',
        name='Beruházási költség',
        line=dict(color='red', width=2, dash='dash'),
        hovertemplate='%{x:.1f} hónap<br>%{y:,.0f} Ft<extra></extra>'
    ))
    
    if payback_months <= max(days_range) / 30:
        fig_payback.add_trace(go.Scatter(
            x=[payback_months],
            y=[investment_cost],
            mode='markers',
            name='Megtérülési pont',
            marker=dict(color='green', size=15, symbol='diamond', line=dict(width=2, color='darkgreen')),
            hovertemplate=f'Megtérülés: {payback_months:.1f} hónap<br>{investment_cost:,.0f} Ft<extra></extra>'
        ))
    
    fig_payback.update_layout(
        title="Beruházás megtérülési görbe",
        xaxis_title="Idő (hónap)",
        yaxis_title="Összeg (Ft)",
        hovermode='x unified',
        template="plotly_white",
        height=500,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    
    st.plotly_chart(fig_payback, use_container_width=True)

"""Érzékenységvizsgálat diagram létrehozása. Megjeleníti a megtérülési időt a különböző ár változások esetén."""
def _create_sensitivity_chart(price_changes, payback_months, base_daily_savings, investment_cost):
    sensitivity_results = []
    payback_days = investment_cost / base_daily_savings
    
    for price_change_pct in price_changes:
        new_daily_savings = base_daily_savings * (1 + price_change_pct / 100)
        if new_daily_savings > 0:
            new_payback_days = investment_cost / new_daily_savings
            new_payback_months = new_payback_days / 30
            sensitivity_results.append({
                'Ár változás (%)': price_change_pct,
                'Megtérülési idő (hónap)': new_payback_months
            })
        else:
            sensitivity_results.append({
                'Ár változás (%)': price_change_pct,
                'Megtérülési idő (hónap)': MAX_PAYBACK_MONTHS
            })
    
    all_results = []
    for r in sensitivity_results:
        result = r.copy()
        if result['Megtérülési idő (hónap)'] == float('inf'):
            result['Megtérülési idő (hónap)'] = MAX_PAYBACK_MONTHS
        all_results.append(result)
    
    if all_results:
        price_changes_all = [r['Ár változás (%)'] for r in all_results]
        payback_months_all = [r['Megtérülési idő (hónap)'] for r in all_results]
        colors = ['red' if r['Megtérülési idő (hónap)'] == MAX_PAYBACK_MONTHS else '#1f77b4' for r in all_results]
        
        fig_sensitivity = go.Figure()
        fig_sensitivity.add_trace(go.Scatter(
            x=price_changes_all,
            y=payback_months_all,
            mode='lines+markers',
            name='Megtérülési idő',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=8, color=colors),
            hovertemplate='Ár változás: %{x:.1f}%<br>Megtérülési idő: %{y:.2f} hónap<extra></extra>'
        ))
        fig_sensitivity.add_trace(go.Scatter(
            x=[0],
            y=[payback_months],
            mode='markers',
            name='Alapértelmezett (jelenlegi ár)',
            marker=dict(color='green', size=15, symbol='diamond', line=dict(width=2, color='darkgreen')),
            hovertemplate=f'Alapértelmezett ár<br>Megtérülési idő: {payback_months:.2f} hónap<extra></extra>'
        ))
        
        x_min = min(price_changes_all) if price_changes_all else -300
        x_max = max(price_changes_all) if price_changes_all else 300
        x_range = [x_min - (x_max - x_min) * 0.05, x_max + (x_max - x_min) * 0.05]
        y_max = max(payback_months_all) if payback_months_all else MAX_PAYBACK_MONTHS
        y_range = [0, y_max * 1.1]
        
        fig_sensitivity.update_layout(
            title="Érzékenységvizsgálat: Energiaár változások hatása a megtérülési időre",
            xaxis_title="Ár változás (%)",
            yaxis_title="Megtérülési idő (hónap)",
            hovermode='x unified',
            template="plotly_white",
            height=500,
            xaxis=dict(range=x_range, autorange=False),
            yaxis=dict(range=y_range, autorange=False),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        
        st.plotly_chart(fig_sensitivity, use_container_width=True)


"""Megtérülési vizsgálat kezelése."""
def _handle_payback_analysis(daily_savings_smart_vs_thermo, investment_cost):
    if investment_cost > 0 and daily_savings_smart_vs_thermo > 0:
        payback_days = investment_cost / daily_savings_smart_vs_thermo
        payback_months = payback_days / 30
        payback_years = payback_days / 365
        payback_date = datetime.now() + timedelta(days=int(payback_days))
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Megtérülési idő (nap)", f"{payback_days:.1f}")
        with col2:
            st.metric("Megtérülési idő (hónap)", f"{payback_months:.1f}")
        with col3:
            st.metric("Megtérülési idő (év)", f"{payback_years:.2f}")
        
        st.write(f"**Becsült megtérülési dátum:** {payback_date.strftime('%Y-%m-%d')}")
        
        st.write("### Megtérülési görbe")
        _create_payback_chart(payback_days, payback_months, investment_cost, daily_savings_smart_vs_thermo)
        
        sensitivity_input = st.session_state.get('sensitivity_price_changes', 
                                                '-300,-200,-100,-50,-20,-10,0,10,20,50,100,200,300')
        try:
            price_changes = [float(x.strip()) for x in sensitivity_input.split(',') if x.strip()]
            price_changes = sorted(price_changes)
            if len(price_changes) == 0:
                st.warning("Kérjük, adjon meg legalább egy ár változást a sidebar-ban!")
                price_changes = [0]
        except Exception as e:
            st.warning(f"Érvénytelen formátum az ár változásokhoz: {e}.")
            price_changes = [0]
        
        st.write("#### Érzékenységvizsgálat diagram")
        _create_sensitivity_chart(price_changes, payback_months, daily_savings_smart_vs_thermo, investment_cost)
    
    elif investment_cost > 0 and daily_savings_smart_vs_thermo <= 0:
        st.warning("A dinamikus fűtésvezérlő jelenleg nem takarít meg pénzt a termosztátos vezérlőhöz képest, így a beruházás nem térül meg.")
    elif investment_cost == 0:
        st.info("Kérjük, adjon meg egy beruházási költséget a sidebar-ban a megtérülési számítás megjelenítéséhez.")

"""Fogyasztási és költség megtakarítások számítása és megjelenítése."""
def show_consumption_cost_savings(start_date, end_date):
    st.write("## Fogyasztási és költség megtakarítások")
    
    if 'loss_prices' not in st.session_state or st.session_state.loss_prices is None:
        st.warning("Az összehasonlításhoz szükségesek az E.ON árak!")
        return
    
    heater_power = st.session_state.get('heater_power', None)
    if heater_power is None or heater_power <= 0:
        st.warning("Kérjük, adjon meg egy érvényes beépített fűtőtest teljesítményt a navigációs sávban!")
        return
    
    with st.spinner("Összehasonlítás számítása..."):
        try:
            smart_query = get_smart_controller_data(start_date, end_date)
            thermostat_query = get_thermostat_controller_data(start_date, end_date)
            smart_data = execute_query(smart_query)
            thermostat_data = execute_query(thermostat_query)
            
            if not (smart_data and thermostat_data and len(smart_data) > 0 and len(thermostat_data) > 0):
                st.warning("Nincs elegendő adat az összehasonlításhoz!")
                return
            
            smart_df, thermostat_df = _prepare_dataframes(smart_data, thermostat_data)
            smart_daily_energy_df, thermostat_daily_energy_df = _calculate_daily_energy(smart_df, thermostat_df)
            
            loss_price_2024, loss_price_2025 = _parse_loss_prices()
            if loss_price_2024 is None or loss_price_2025 is None:
                st.error("Nem sikerült kiszámítani a költségeket.")
                return
            
            smart_daily_energy = smart_daily_energy_df['daily_energy_kwh'].mean()
            thermostat_daily_energy = thermostat_daily_energy_df['daily_energy_kwh'].mean()
            heater_daily_energy = (heater_power * HEATER_USAGE_HOURS) / 1000.0
            
            smart_loss_cost, thermostat_loss_cost, heater_loss_cost, total_days = _calculate_costs(
                smart_daily_energy_df, thermostat_daily_energy_df, heater_daily_energy,
                loss_price_2024, loss_price_2025
            )
            
            smart_savings_cost, thermostat_savings_cost, smart_savings_energy, thermostat_savings_energy = \
                _calculate_savings(smart_daily_energy_df, thermostat_daily_energy_df, heater_daily_energy,
                                 loss_price_2024, loss_price_2025, total_days)
            
            smart_vs_thermo_savings_energy, smart_vs_thermo_savings_cost, smart_thermo_comparison = \
                _calculate_smart_vs_thermo_savings(smart_daily_energy_df, thermostat_daily_energy_df,
                                                  loss_price_2024, loss_price_2025)
            
            consumption_diff_smart_heater = smart_daily_energy - heater_daily_energy
            consumption_diff_thermo_heater = thermostat_daily_energy - heater_daily_energy
            consumption_diff_smart_thermo = smart_daily_energy - thermostat_daily_energy
            
            cost_diff_smart_heater = -smart_savings_cost
            cost_diff_thermo_heater = -thermostat_savings_cost
            cost_diff_smart_thermo = -smart_vs_thermo_savings_cost
            
            yearly_diff_smart_heater = cost_diff_smart_heater * 365
            yearly_diff_thermo_heater = cost_diff_thermo_heater * 365
            yearly_diff_smart_thermo = cost_diff_smart_thermo * 365
            
            _display_controller_table(smart_daily_energy_df, thermostat_daily_energy_df,
                                     loss_price_2024, loss_price_2025)
            _display_heater_metrics(smart_daily_energy_df, heater_daily_energy,
                                   loss_price_2024, loss_price_2025)
            
            st.write("---")
            st.write("")
            st.write("## Összehasonlítás")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                st.write("**Vezérlők kiválasztása:**")
                current_smart = st.session_state.get("savings_smart_checkbox", False)
                current_thermo = st.session_state.get("savings_thermo_checkbox", False)
                current_heater = st.session_state.get("savings_heater_checkbox", False)
                current_count = sum([current_smart, current_thermo, current_heater])
                
                smart_selected = st.checkbox(
                    "Dinamikus fűtésvezérlő",
                    key="savings_smart_checkbox",
                    disabled=(current_count == 2 and not current_smart)
                )
                
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
                
                current_count_after_thermo = sum([
                    st.session_state.get("savings_smart_checkbox", False),
                    st.session_state.get("savings_thermo_checkbox", False),
                    current_heater
                ])
                
                heater_selected = st.checkbox(
                    "Folyamatos működés esetén",
                    key="savings_heater_checkbox",
                    disabled=(current_count_after_thermo == 2 and not current_heater)
                )
            
            selected_count = sum([smart_selected, thermo_selected, heater_selected])
            
            if selected_count == 2:
                comparison_title, energy_savings_energy, energy_savings_cost, note_text = \
                    _get_comparison_data(smart_selected, thermo_selected, heater_selected,
                                       smart_savings_energy, smart_savings_cost,
                                       thermostat_savings_energy, thermostat_savings_cost,
                                       smart_vs_thermo_savings_energy, smart_vs_thermo_savings_cost,
                                       consumption_diff_smart_heater, consumption_diff_thermo_heater,
                                       consumption_diff_smart_thermo)
                
                if comparison_title:
                    st.write(f"#### {comparison_title}")
                    if note_text:
                        st.write(note_text)
                    st.write("##### Energiaár megtakarítás")
                    _display_comparison_table(energy_savings_energy, energy_savings_cost)
            elif selected_count != 2:
                st.info("Kérjük, válasszon ki 2 vezérlőt az összehasonlításhoz!")
            
            st.write("---")
            st.write("")
            st.write("### Összefoglaló")
            _display_summary_table(smart_daily_energy_df, thermostat_daily_energy_df,
                                  smart_thermo_comparison, heater_daily_energy,
                                  yearly_diff_smart_heater, yearly_diff_thermo_heater, yearly_diff_smart_thermo)
            
            investment_cost = st.session_state.get('investment_cost', 0.0)
            daily_savings_smart_vs_thermo = smart_vs_thermo_savings_cost if smart_vs_thermo_savings_cost > 0 else 0
            _handle_payback_analysis(daily_savings_smart_vs_thermo, investment_cost)
            
        except Exception as e:
            st.error(f"Hiba az összehasonlítás során: {e}")
