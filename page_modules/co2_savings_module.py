import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_services.co2_calculation import fetch_co2_emission_data


TABLE_OPTIONS = {
    "dfv_smart_db": "Dinamikus fűtésvezérlő",
    "dfv_termosztat_db": "Termosztátos vezérlő"
}

"""Inicializálja a cache változókat. Ha nincs cache-elve akkor inicializálja a változókat."""
def _initialize_cache():
    if 'co2_cached_days' not in st.session_state:
        st.session_state.co2_cached_days = 10
    if 'co2_cached_heater_power' not in st.session_state:
        st.session_state.co2_cached_heater_power = None
    if 'co2_cached_table' not in st.session_state:
        st.session_state.co2_cached_table = None

"""Törli a CO2 cache-t. Ha a cache-elt adatok változnak, akkor törli a cache-et."""
def _clear_cache():
    cache_keys = [
        'co2_hourly_dataframe', 'co2_hourly_with_power', 'co2_daily_dataframe',
        'co2_daily_dataframe_smart', 'co2_daily_dataframe_thermo', 'power_co2_pairs'
    ]
    for key in cache_keys:
        if key in st.session_state:
            del st.session_state[key]

"""Frissíti a cache-t, ha változott a fűtőteljesítmény vagy a tábla."""
def _update_cache_if_needed(selected_table, heater_power):
    current_heater_power = st.session_state.get('heater_power', None)
    if (st.session_state.co2_cached_heater_power != current_heater_power) or \
       (st.session_state.co2_cached_table != selected_table):
        _clear_cache()
        st.session_state.co2_cached_heater_power = current_heater_power
        st.session_state.co2_cached_table = selected_table

"""Lekéri mindkét tábla adatait a diagramhoz. Ha már van cache-elve akkor nem kéri le újra."""
def _fetch_all_table_data(heater_power, days_to_show=10):
    if ('co2_daily_dataframe_smart' in st.session_state) and \
       ('co2_daily_dataframe_thermo' in st.session_state):
        return
    
    with st.spinner("CO2 adatok lekérése folyamatban..."):
        result_smart = fetch_co2_emission_data(days_to_show, None, "dfv_smart_db", heater_power)
        result_thermo = fetch_co2_emission_data(days_to_show, None, "dfv_termosztat_db", heater_power)
        
        if result_smart and len(result_smart) >= 3 and result_smart[2] is not None:
            st.session_state['co2_daily_dataframe_smart'] = result_smart[2]
        
        if result_thermo and len(result_thermo) >= 3 and result_thermo[2] is not None:
            st.session_state['co2_daily_dataframe_thermo'] = result_thermo[2]

"""Lekéri a kiválasztott tábla adatait. Ha már van cache-elve akkor nem kéri le újra."""
def _fetch_selected_table_data(selected_table, heater_power, days_to_show=10):
    if ('co2_hourly_dataframe' in st.session_state) and \
       ('co2_daily_dataframe' in st.session_state) and \
       (st.session_state.co2_cached_table == selected_table):
        return
    
    with st.spinner("CO2 adatok lekérése folyamatban..."):
        result = fetch_co2_emission_data(days_to_show, None, selected_table, heater_power)
        
        if result and len(result) >= 3:
            if result[0] is not None:
                st.session_state['co2_hourly_dataframe'] = result[0]
                st.session_state['co2_cached_days'] = days_to_show
                st.session_state['co2_cached_table'] = selected_table
            
            if result[1] is not None and result[2] is not None:
                st.session_state['co2_hourly_with_power'] = result[1]
                st.session_state['co2_daily_dataframe'] = result[2]
                if len(result) > 3 and result[3] is not None:
                    st.session_state['power_co2_pairs'] = result[3]

"""Kiszámítja a hagyományos fűtőtest CO2 kibocsátását"""
def _calculate_heater_co2(co2_hourly_df, heater_power):
    hourly_energy_kwh = heater_power / 1000.0
    co2_hourly_df_copy = co2_hourly_df.copy()
    co2_hourly_df_copy['Izzó_energia_kWh'] = hourly_energy_kwh
    co2_hourly_df_copy['Izzó_CO2_g'] = co2_hourly_df_copy['Izzó_energia_kWh'] * \
                                       co2_hourly_df_copy['CO2 Kibocsátás (g CO2/kWh)']
    
    heater_daily_co2 = co2_hourly_df_copy.groupby('Dátum').agg({
        'Izzó_CO2_g': 'sum'
    }).reset_index()
    heater_daily_co2.columns = ['Dátum', 'Folyamatos működés esetén napi CO2 (g)']
    
    return heater_daily_co2

"""Létrehozza az összehasonlító DataFrame-et."""
def _create_comparison_df(daily_co2_df, heater_daily_co2):
    comparison_df = pd.merge(
        daily_co2_df[['Dátum', 'Napi CO2 (g)']],
        heater_daily_co2,
        on='Dátum',
        how='inner'
    )
    comparison_df['CO2 megtakarítás (g)'] = comparison_df['Folyamatos működés esetén napi CO2 (g)'] - \
                                            comparison_df['Napi CO2 (g)']
    comparison_df['Megtakarítás százalék'] = (comparison_df['CO2 megtakarítás (g)'] / \
                                              comparison_df['Folyamatos működés esetén napi CO2 (g)']) * 100
    
    return comparison_df

"""Megjeleníti az összesített metrikákat."""
def _display_summary_metrics(comparison_df, selected_table_display_name):
    st.write("### Összesített eredmények")
    
    total_database_co2 = comparison_df['Napi CO2 (g)'].sum() / 1000.0
    total_heater_co2 = comparison_df['Folyamatos működés esetén napi CO2 (g)'].sum() / 1000.0
    total_savings = comparison_df['CO2 megtakarítás (g)'].sum() / 1000.0
    avg_savings_percent = comparison_df['Megtakarítás százalék'].mean()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(f"{selected_table_display_name} összes CO2 kibocsátása (éves)", f"{total_database_co2:.2f} kg")
    with col2:
        st.metric("Folyamatos működés esetén összes CO2 kibocsátása (éves)", f"{total_heater_co2:.2f} kg")
    with col3:
        st.metric("Összes megtakarítás", f"{total_savings:.2f} kg", delta=f"{avg_savings_percent:.2f}%")
    with col4:
        st.metric("Átlagos CO2 megtakarítás naponta", f"{total_savings / len(comparison_df):.2f} kg")

"""Inicializálja a lapozást a táblázatban."""
def _initialize_pagination():
    if "co2_savings_page_size" not in st.session_state:
        st.session_state.co2_savings_page_size = 5
    if "prev_co2_savings_page_size" not in st.session_state:
        st.session_state.prev_co2_savings_page_size = st.session_state.co2_savings_page_size
    if "co2_savings_table_offset" not in st.session_state:
        st.session_state.co2_savings_table_offset = 0

"""Megjeleníti a lapozás vezérlőket."""
def _display_pagination_controls(total_rows, current_page_size):
    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 0.2, 0.2, 0.2, 0.2, 0.1, 0.3])
    
    with col2:
        if st.button("⏮️", key="co2_savings_first_page"):
            st.session_state.co2_savings_table_offset = 0
            st.rerun()
    
    with col3:
        if st.button("⬅️", key="co2_savings_prev_page"):
            if st.session_state.co2_savings_table_offset >= current_page_size:
                st.session_state.co2_savings_table_offset -= current_page_size
                st.rerun()
    
    with col4:
        next_offset = st.session_state.co2_savings_table_offset + current_page_size
        has_next_page = next_offset < total_rows
        if st.button("➡️", disabled=not has_next_page, key="co2_savings_next_page"):
            st.session_state.co2_savings_table_offset = next_offset
            st.rerun()
    
    with col5:
        last_page_offset = ((total_rows - 1) // current_page_size) * current_page_size
        is_on_last_page = st.session_state.co2_savings_table_offset >= last_page_offset
        if st.button("⏭️", disabled=is_on_last_page, key="co2_savings_last_page"):
            st.session_state.co2_savings_table_offset = last_page_offset
            st.rerun()
    
    with col7:
        current_page = (st.session_state.co2_savings_table_offset // current_page_size) + 1
        total_pages = (total_rows + current_page_size - 1) // current_page_size
        st.write(f" **Oldal:** {current_page} / {total_pages}")


"""Megjeleníti az összehasonlító táblázatot a gombokkal."""
def _display_comparison_table(comparison_df, selected_table_display_name):
    st.write("### Részletes napi összehasonlítás")
    
    _initialize_pagination()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        page_size_options = [5, 15, 25]
        current_co2_savings_page_size = st.session_state.co2_savings_page_size
        try:
            current_index = page_size_options.index(current_co2_savings_page_size)
        except ValueError:
            current_index = 0
        
        co2_savings_page_size = st.selectbox(
            "Elemek száma:",
            page_size_options,
            index=current_index,
            key="co2_savings_page_size_selector"
        )
        
        if co2_savings_page_size != st.session_state.prev_co2_savings_page_size:
            st.session_state.co2_savings_table_offset = 0
            st.session_state.prev_co2_savings_page_size = co2_savings_page_size
        
        st.session_state.co2_savings_page_size = co2_savings_page_size
    
    display_comparison = comparison_df[['Dátum', 'Napi CO2 (g)', 'Folyamatos működés esetén napi CO2 (g)', 
                                        'CO2 megtakarítás (g)', 'Megtakarítás százalék']].copy()
    display_comparison['Napi CO2 (g)'] = display_comparison['Napi CO2 (g)'] / 1000.0
    display_comparison['Folyamatos működés esetén napi CO2 (g)'] = display_comparison['Folyamatos működés esetén napi CO2 (g)'] / 1000.0
    display_comparison['CO2 megtakarítás (g)'] = display_comparison['CO2 megtakarítás (g)'] / 1000.0
    display_comparison.columns = ['Dátum', f'{selected_table_display_name} CO2 kibocsátás (kg)', 
                                  'Folyamatos működés esetén CO2 kibocsátás (kg)', 'Megtakarítás (kg)', 'Megtakarítás (%)']
    
    display_comparison['Dátum'] = pd.to_datetime(display_comparison['Dátum']).dt.strftime('%Y-%m-%d')
    
    for col in [f'{selected_table_display_name} CO2 kibocsátás (kg)', 'Folyamatos működés esetén CO2 kibocsátás (kg)', 
                'Megtakarítás (kg)', 'Megtakarítás (%)']:
        if col in display_comparison.columns:
            display_comparison[col] = pd.to_numeric(display_comparison[col], errors='coerce').round(2)
    
    total_rows = len(display_comparison)
    current_page_size = st.session_state.co2_savings_page_size
    start_idx = st.session_state.co2_savings_table_offset
    end_idx = min(start_idx + current_page_size, total_rows)
    display_comparison_paginated = display_comparison.iloc[start_idx:end_idx]
    
    st.dataframe(display_comparison_paginated, use_container_width=True, hide_index=True)
    _display_pagination_controls(total_rows, current_page_size)


"""Létrehozza az összehasonlító diagramot (vonal diagram)."""
def _create_comparison_chart(comparison_df, heater_daily_co2):
    st.write("### Vizuális összehasonlítás")
    fig_comparison = go.Figure()
    
    comparison_df_kg = comparison_df.copy()
    comparison_df_kg['Folyamatos működés esetén napi CO2 (g)'] = \
        comparison_df_kg['Folyamatos működés esetén napi CO2 (g)'] / 1000.0
    
    if 'co2_daily_dataframe_smart' in st.session_state and st.session_state['co2_daily_dataframe_smart'] is not None:
        daily_co2_df_smart = st.session_state['co2_daily_dataframe_smart']
        smart_comparison = pd.merge(
            daily_co2_df_smart[['Dátum', 'Napi CO2 (g)']],
            heater_daily_co2,
            on='Dátum',
            how='inner'
        )
        smart_comparison['Napi CO2 (g)'] = smart_comparison['Napi CO2 (g)'] / 1000.0
        
        fig_comparison.add_trace(go.Scatter(
            x=smart_comparison['Dátum'],
            y=smart_comparison['Napi CO2 (g)'],
            mode='lines+markers',
            name='Dinamikus fűtésvezérlő CO2 kibocsátás',
            line=dict(color='blue', width=2),
            marker=dict(size=6)
        ))
    
    if 'co2_daily_dataframe_thermo' in st.session_state and st.session_state['co2_daily_dataframe_thermo'] is not None:
        daily_co2_df_thermo = st.session_state['co2_daily_dataframe_thermo']
        thermo_comparison = pd.merge(
            daily_co2_df_thermo[['Dátum', 'Napi CO2 (g)']],
            heater_daily_co2,
            on='Dátum',
            how='inner'
        )
        thermo_comparison['Napi CO2 (g)'] = thermo_comparison['Napi CO2 (g)'] / 1000.0
        
        fig_comparison.add_trace(go.Scatter(
            x=thermo_comparison['Dátum'],
            y=thermo_comparison['Napi CO2 (g)'],
            mode='lines+markers',
            name='Termosztátos vezérlő CO2 kibocsátás',
            line=dict(color='green', width=2),
            marker=dict(size=6)
        ))
    
    fig_comparison.add_trace(go.Scatter(
        x=comparison_df_kg['Dátum'],
        y=comparison_df_kg['Folyamatos működés esetén napi CO2 (g)'],
        mode='lines',
        name='Folyamatos működés esetén CO2 kibocsátás',
        line=dict(color='red', width=1.5, dash='dash')
    ))
    
    fig_comparison.update_layout(
        title="CO2 Kibocsátás összehasonlítás: Dinamikus fűtésvezérlő vs Termosztátos vezérlő vs Folyamatos működés esetén",
        xaxis_title="Dátum",
        yaxis_title="CO2 Kibocsátás (kg)",
        hovermode='x unified',
        template="plotly_white",
        height=500
    )
    
    st.plotly_chart(fig_comparison, use_container_width=True)

"""Előkészíti a hőtérkép adatait."""
def _prepare_heatmap_data(comparison_type, heater_daily_co2):
    if comparison_type == "Dinamikus vs Termosztátos":
        if 'co2_daily_dataframe_smart' in st.session_state and st.session_state['co2_daily_dataframe_smart'] is not None and \
           'co2_daily_dataframe_thermo' in st.session_state and st.session_state['co2_daily_dataframe_thermo'] is not None:
            daily_co2_df_smart = st.session_state['co2_daily_dataframe_smart']
            daily_co2_df_thermo = st.session_state['co2_daily_dataframe_thermo']
            
            selected_comparison = pd.merge(
                daily_co2_df_smart[['Dátum', 'Napi CO2 (g)']],
                daily_co2_df_thermo[['Dátum', 'Napi CO2 (g)']],
                on='Dátum',
                how='inner',
                suffixes=('_smart', '_thermo')
            )
            selected_comparison['CO2 megtakarítás (g)'] = selected_comparison['Napi CO2 (g)_thermo'] - \
                                                          selected_comparison['Napi CO2 (g)_smart']
            selected_comparison['CO2 megtakarítás (kg)'] = selected_comparison['CO2 megtakarítás (g)'] / 1000.0
            return selected_comparison, "Dinamikus vs Termosztátos"
        else:
            st.warning("Nincs elegendő adat a Dinamikus vs Termosztátos összehasonlításhoz!")
            return None, None
    
    elif comparison_type == "Dinamikus vs Folyamatos működés":
        if 'co2_daily_dataframe_smart' in st.session_state and st.session_state['co2_daily_dataframe_smart'] is not None:
            daily_co2_df_smart = st.session_state['co2_daily_dataframe_smart']
            selected_comparison = pd.merge(
                daily_co2_df_smart[['Dátum', 'Napi CO2 (g)']],
                heater_daily_co2,
                on='Dátum',
                how='inner'
            )
            selected_comparison['CO2 megtakarítás (g)'] = selected_comparison['Folyamatos működés esetén napi CO2 (g)'] - \
                                                          selected_comparison['Napi CO2 (g)']
            selected_comparison['CO2 megtakarítás (kg)'] = selected_comparison['CO2 megtakarítás (g)'] / 1000.0
            return selected_comparison, "Dinamikus vs Folyamatos működés"
        else:
            st.warning("Nincs elegendő adat a Dinamikus vs Folyamatos működés összehasonlításhoz!")
            return None, None
    
    elif comparison_type == "Termosztátos vs Folyamatos működés":
        if 'co2_daily_dataframe_thermo' in st.session_state and st.session_state['co2_daily_dataframe_thermo'] is not None:
            daily_co2_df_thermo = st.session_state['co2_daily_dataframe_thermo']
            selected_comparison = pd.merge(
                daily_co2_df_thermo[['Dátum', 'Napi CO2 (g)']],
                heater_daily_co2,
                on='Dátum',
                how='inner'
            )
            selected_comparison['CO2 megtakarítás (g)'] = selected_comparison['Folyamatos működés esetén napi CO2 (g)'] - \
                                                          selected_comparison['Napi CO2 (g)']
            selected_comparison['CO2 megtakarítás (kg)'] = selected_comparison['CO2 megtakarítás (g)'] / 1000.0
            return selected_comparison, "Termosztátos vs Folyamatos működés"
        else:
            st.warning("Nincs elegendő adat a Termosztátos vs Folyamatos működés összehasonlításhoz!")
            return None, None
    
    return None, None

"""Megjeleníti a hőtérképet."""
def _display_heatmap(comparison_type, heater_daily_co2):
    st.write("### Megtakarítás hőtérkép")
    
    comparison_type_select = st.selectbox(
        "Összehasonlítás típusa:",
        options=["Dinamikus vs Termosztátos", "Dinamikus vs Folyamatos működés", "Termosztátos vs Folyamatos működés"],
        key="heatmap_comparison_type"
    )
    
    selected_comparison, comparison_title = _prepare_heatmap_data(comparison_type_select, heater_daily_co2)
    
    if selected_comparison is not None and not selected_comparison.empty:
        selected_comparison['Dátum'] = pd.to_datetime(selected_comparison['Dátum'])
        selected_comparison['Év'] = selected_comparison['Dátum'].dt.year
        selected_comparison['Hónap'] = selected_comparison['Dátum'].dt.month
        selected_comparison['Nap'] = selected_comparison['Dátum'].dt.day
        
        heatmap_data = selected_comparison.pivot_table(
            values='CO2 megtakarítás (kg)',
            index='Nap',
            columns='Hónap',
            aggfunc='mean'
        )
        
        month_names = ['Jan', 'Feb', 'Már', 'Ápr', 'Máj', 'Jún', 'Júl', 'Aug', 'Sze', 'Okt', 'Nov', 'Dec']
        available_months = heatmap_data.columns.tolist()
        heatmap_data.columns = [month_names[m-1] if m <= 12 else f'Hónap {m}' for m in available_months]
        
        fig_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='Greens',
            colorbar=dict(title="CO2 megtakarítás (kg)"),
            hovertemplate='Nap: %{y}<br>Hónap: %{x}<br>Megtakarítás: %{z:.2f} kg<extra></extra>'
        ))
        
        fig_heatmap.update_layout(
            title=f"Napi CO2 megtakarítás hőtérkép - {comparison_title}",
            xaxis_title="Hónap",
            yaxis_title="Nap",
            template="plotly_white",
            height=600
        )
        
        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.warning("Nincs elegendő adat a hőtérképhez!")


"""CO2 megtakarítások számítása és megjelenítése."""
def show_co2_savings():
    st.write("## CO2 megtakarítás számítása")
    
    col1, col2 = st.columns(2)
    with col1:
        selected_table = st.selectbox(
            "Válassz táblát:",
            options=list(TABLE_OPTIONS.keys()),
            format_func=lambda x: TABLE_OPTIONS[x],
            key="co2_table_selector"
        )
    
    selected_table_display_name = TABLE_OPTIONS[selected_table]
    heater_power = st.session_state.get('heater_power', None)
    
    if heater_power is None or heater_power <= 0:
        st.warning("⚠️ Kérjük, adjon meg egy érvényes hagyományos fűtőtest teljesítményt a navigációs sávban!")
        return
    
    _initialize_cache()
    _update_cache_if_needed(selected_table, heater_power)
    
    _fetch_all_table_data(heater_power)
    _fetch_selected_table_data(selected_table, heater_power)
    
    if 'co2_hourly_dataframe' not in st.session_state or st.session_state['co2_hourly_dataframe'] is None:
        st.warning("Nincs elegendő adat az összehasonlításhoz. Kérjük, várjon, amíg a CO2 adatok betöltődnek.")
        return
    
    co2_hourly_df = st.session_state['co2_hourly_dataframe']
    heater_daily_co2 = _calculate_heater_co2(co2_hourly_df, heater_power)
    
    if 'co2_daily_dataframe' not in st.session_state or st.session_state['co2_daily_dataframe'] is None:
        st.warning("Nincs elegendő adat az összehasonlításhoz. Kérjük, várjon, amíg a CO2 adatok betöltődnek.")
        return
    
    daily_co2_df = st.session_state['co2_daily_dataframe']
    comparison_df = _create_comparison_df(daily_co2_df, heater_daily_co2)
    
    _display_summary_metrics(comparison_df, selected_table_display_name)
    _display_comparison_table(comparison_df, selected_table_display_name)
    _create_comparison_chart(comparison_df, heater_daily_co2)
    _display_heatmap(None, heater_daily_co2)
