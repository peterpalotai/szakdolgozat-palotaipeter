

# ============================================================================
# Fogyasztási és költség megtakarítások lekérdezései
# ============================================================================

def get_smart_controller_data(start_date: str, end_date: str) -> str:
    """
    Dinamikus fűtésvezérlő adatainak lekérdezése.
    
    Args:
        start_date: Kezdő dátum (YYYY-MM-DD formátum)
        end_date: Vég dátum (YYYY-MM-DD formátum)
    
    Returns:
        SQL lekérdezés string
    """
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


def get_thermostat_controller_data(start_date: str, end_date: str) -> str:
    """
    Termosztátos vezérlő adatainak lekérdezése.
    
    Args:
        start_date: Kezdő dátum (YYYY-MM-DD formátum)
        end_date: Vég dátum (YYYY-MM-DD formátum)
    
    Returns:
        SQL lekérdezés string
    """
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


# ============================================================================
# CO2 API lekérdezései
# ============================================================================

def get_last_date_from_table(table_name: str) -> str:
    """
    Utolsó dátum lekérdezése egy táblából.
    
    Args:
        table_name: Tábla neve
    
    Returns:
        SQL lekérdezés string
    """
    query = f"SELECT MAX(date) as last_date FROM {table_name}"
    return query


def get_power_data_for_co2(table_name: str, start_date: str, end_date: str) -> str:
    """
    Teljesítmény adatok lekérdezése CO2 számításhoz.
    
    Args:
        table_name: Tábla neve (dfv_smart_db vagy dfv_termosztat_db)
        start_date: Kezdő dátum (YYYY-MM-DD formátum)
        end_date: Vég dátum (YYYY-MM-DD formátum)
    
    Returns:
        SQL lekérdezés string
    """
    # Oszlopnevek meghatározása a táblanév alapján
    if table_name == "dfv_termosztat_db":
        power_column = "trend_termosztat_p"
    else:  # dfv_smart_db
        power_column = "trend_smart_p"
    
    query = f"""
    SELECT date, time, {power_column} as power_W
    FROM {table_name}
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    AND {power_column} IS NOT NULL
    ORDER BY date, time
    """
    return query


# ============================================================================
# Főoldal lekérdezései
# ============================================================================

def get_table_data_paginated(table_name: str, columns: str, page_size: int, offset: int) -> str:
    """
    Tábla adatok lekérdezése lapozással.
    
    Args:
        table_name: Tábla neve
        columns: Oszlopok listája (vesszővel elválasztva)
        page_size: Oldalankénti rekordok száma
        offset: Eltolás
    
    Returns:
        SQL lekérdezés string
    """
    query = f"SELECT {columns} FROM {table_name} LIMIT {page_size} OFFSET {offset}"
    return query


def get_table_count(table_name: str) -> str:
    """
    Tábla rekordjainak számának lekérdezése.
    
    Args:
        table_name: Tábla neve
    
    Returns:
        SQL lekérdezés string
    """
    query = f"SELECT COUNT(*) FROM {table_name}"
    return query


def get_chart_data_by_time_range(table_name: str, columns: str, start_time: str, end_time: str) -> str:
    """
    Diagram adatok lekérdezése időintervallum alapján.
    
    Args:
        table_name: Tábla neve
        columns: Oszlopok listája (vesszővel elválasztva)
        start_time: Kezdő dátum-idő (YYYY-MM-DD HH:MM:SS formátum)
        end_time: Vég dátum-idő (YYYY-MM-DD HH:MM:SS formátum)
    
    Returns:
        SQL lekérdezés string
    """
    query = f"""
    SELECT {columns} FROM {table_name} 
    WHERE (date::text || ' ' || time::text)::timestamp <= '{end_time}'::timestamp
    AND (date::text || ' ' || time::text)::timestamp >= '{start_time}'::timestamp
    ORDER BY date, time
    """
    return query


# ============================================================================
# Energia előrejelzés lekérdezései
# ============================================================================

def get_energy_prediction_data(table_name: str, start_date: str, end_date: str) -> str:
    """
    Energia előrejelzéshez szükséges adatok lekérdezése.
    
    Args:
        table_name: Tábla neve (dfv_smart_db vagy dfv_termosztat_db)
        start_date: Kezdő dátum (YYYY-MM-DD formátum)
        end_date: Vég dátum (YYYY-MM-DD formátum)
    
    Returns:
        SQL lekérdezés string
    """
    
    if table_name == "dfv_smart_db":
        power_column = "trend_smart_p"
        current_column = "trend_smart_i1"
        temp_column = "trend_smart_t"
        humidity_column = "trend_smart_rh"
    else:  # dfv_termosztat_db
        power_column = "trend_termosztat_p"
        current_column = "trend_termosztat_i1"
        temp_column = "trend_termosztat_t"
        humidity_column = "trend_termosztat_rh"
    
    query = f"""
    SELECT date, time, 
           {power_column} as value,
           {current_column} as current,
           {temp_column} as internal_temp,
           trend_kulso_homerseklet_pillanatnyi as external_temp,
           {humidity_column} as internal_humidity,
           trend_kulso_paratartalom as external_humidity
    FROM {table_name}
    WHERE DATE(date) BETWEEN '{start_date}' AND '{end_date}'
    AND {power_column} IS NOT NULL 
    AND {current_column} IS NOT NULL
    AND {temp_column} IS NOT NULL
    AND trend_kulso_homerseklet_pillanatnyi IS NOT NULL
    ORDER BY date, time
    """
    return query

