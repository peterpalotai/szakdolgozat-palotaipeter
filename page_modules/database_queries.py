"""Teljesítmény oszlop nevének meghatározása (mapping)."""
def _get_power_column(table_name: str) -> str:
    return "trend_termosztat_p" if table_name == "dfv_termosztat_db" else "trend_smart_p"


"""Vezérlő oszlopnevek meghatározása (mapping)."""
def _get_controller_columns(table_name: str) -> dict:
    if table_name == "dfv_smart_db":
        return {
            'power': 'trend_smart_p',
            'current': 'trend_smart_i1',
            'temp': 'trend_smart_t',
            'humidity': 'trend_smart_rh'
        }
    else:
        return {
            'power': 'trend_termosztat_p',
            'current': 'trend_termosztat_i1',
            'temp': 'trend_termosztat_t',
            'humidity': 'trend_termosztat_rh'
        }

"""Dinamikus fűtésvezérlő adatainak lekérdezése."""
def get_smart_controller_data(start_date: str, end_date: str) -> str:
    query = f"""
    SELECT date, time, 
           trend_smart_p as value,
           trend_smart_i1 as current,
           trend_smart_t as internal_temp,
           trend_kulso_homerseklet_pillanatnyi as external_temp,
           trend_smart_rh as internal_humidity,
           trend_kulso_paratartalom as external_humidity
    FROM dfv_smart_db
    WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
    AND trend_smart_p IS NOT NULL 
    AND trend_smart_i1 IS NOT NULL
    AND trend_smart_t IS NOT NULL
    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
    ORDER BY date, time
    """
    return query

"""Termosztátos vezérlő adatainak lekérdezése."""
def get_thermostat_controller_data(start_date: str, end_date: str) -> str:
    query = f"""
    SELECT date, time, 
           trend_termosztat_p as value,
           trend_termosztat_i1 as current,
           trend_termosztat_t as internal_temp,
           trend_kulso_homerseklet_pillanatnyi as external_temp,
           trend_termosztat_rh as internal_humidity,
           trend_kulso_paratartalom as external_humidity
    FROM dfv_termosztat_db
    WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
    AND trend_termosztat_p IS NOT NULL 
    AND trend_termosztat_i1 IS NOT NULL
    AND trend_termosztat_t IS NOT NULL
    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
    ORDER BY date, time
    """
    return query


"""Utolsó dátum lekérdezése egy táblából."""
def get_last_date_from_table(table_name: str) -> str:
    return f"SELECT MAX(date) as last_date FROM {table_name}"


"""Teljesítmény adatok lekérdezése CO2 számításhoz."""
def get_power_data_for_co2(table_name: str, start_date: str, end_date: str) -> str:
    power_column = _get_power_column(table_name)
    return f"""
    SELECT date, time, {power_column} as power_W
    FROM {table_name}
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    AND {power_column} IS NOT NULL
    ORDER BY date, time
    """


"""Tábla adatok lekérdezése lapozással."""
def get_table_data_paginated(table_name: str, columns: str, page_size: int, offset: int) -> str:
    return f"SELECT {columns} FROM {table_name} ORDER BY date, time LIMIT {page_size} OFFSET {offset}"

"""Tábla rekordjainak számának lekérdezése."""
def get_table_count(table_name: str) -> str:
    return f"SELECT COUNT(*) FROM {table_name}"


"""Diagram adatok lekérdezése időintervallum alapján."""
def get_chart_data_by_time_range(table_name: str, columns: str, start_time: str, end_time: str) -> str:
    return f"""
    SELECT {columns} FROM {table_name} 
    WHERE (date::text || ' ' || time::text)::timestamp <= '{end_time}'::timestamp
    AND (date::text || ' ' || time::text)::timestamp >= '{start_time}'::timestamp
    ORDER BY date, time
    """

"""Energia előrejelzéshez szükséges adatok lekérdezése."""
def get_energy_prediction_data(table_name: str, start_date: str, end_date: str) -> str:
    cols = _get_controller_columns(table_name)
    return f"""
    SELECT date, time, 
           {cols['power']} as value,
           {cols['current']} as current,
           {cols['temp']} as internal_temp,
           trend_kulso_homerseklet_pillanatnyi as external_temp,
           {cols['humidity']} as internal_humidity,
           trend_kulso_paratartalom as external_humidity
    FROM {table_name}
    WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
    AND {cols['power']} IS NOT NULL 
    AND {cols['current']} IS NOT NULL
    AND {cols['temp']} IS NOT NULL
    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
    ORDER BY date, time
    """
