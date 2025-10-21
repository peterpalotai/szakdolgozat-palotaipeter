import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

@st.cache_data(ttl=3600)  # Cache for 1 hour
def scrape_eon_prices():
    """Scrape only the two specific values from E.ON pricing page"""
    
    # XPaths for the two data points
    xpath1 = "/html/body/eon-ui-page-wrapper/main/div/eon-ui-section/eon-ui-grid-control/eon-ui-grid-control-column/eon-ui-grid-control/eon-ui-grid-control-column[1]/div[4]/table/tbody/tr[19]/td[3]"
    xpath2 = "/html/body/eon-ui-page-wrapper/main/div/eon-ui-section/eon-ui-grid-control/eon-ui-grid-control-column/eon-ui-grid-control/eon-ui-grid-control-column[1]/eon-ui-grid-control/eon-ui-grid-control-column/div/table/tbody/tr[5]/td[10]"
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = None
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Load only the E.ON page
        driver.get("https://www.eon.hu/hu/lakossagi/aram/arak.html")
        
        # Wait for content to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)
        
        # Get the two values
        value1 = driver.find_element(By.XPATH, xpath1).text
        value2 = driver.find_element(By.XPATH, xpath2).text
        
        # Debug: kiírjuk az árakat
        print(f"Debug - Veszteségi ár: {value1}")
        print(f"Debug - Piaci ár: {value2}")
        
        return value1, value2, None
        
    except Exception as e:
        return None, None, str(e)
    
    finally:
        if driver:
            driver.quit()

def calculate_energy_costs(consumption_data, loss_price, market_price):
    """Számítja az energia költségeket a fogyasztás alapján
    
    Args:
        consumption_data: Napi átlagos fogyasztás Watt-ban (W)
        loss_price: Veszteségi energiaár (Ft/kWh)
        market_price: Piaci energiaár (Ft/kWh)
    
    Returns:
        tuple: (veszteségi_költség, piaci_költség, veszteségi_ár, piaci_ár)
    """
    try:
        # Árak konvertálása számokká (Ft/kWh)
        loss_price_num = float(loss_price.replace(',', '.').replace(' Ft/kWh', ''))
        market_price_num = float(market_price.replace(',', '.').replace(' Ft/kWh', ''))
        
        # Napi átlagos fogyasztás konvertálása kWh-ba
        # consumption_data = napi átlagos teljesítmény Watt-ban (15 perces mérések átlaga)
        # W -> kW: osztás 1000-el
        # kW -> kWh/nap: szorzás 24 órával (napi energia fogyasztás)
        daily_consumption_kwh = (consumption_data / 1000) * 24  # W -> kW -> kWh/nap
        
        # Napi költségek számítása
        daily_loss_cost = daily_consumption_kwh * loss_price_num
        daily_market_cost = daily_consumption_kwh * market_price_num
        
        return daily_loss_cost, daily_market_cost, loss_price_num, market_price_num
    except Exception as e:
        st.error(f"Hiba a költségek számításakor: {e}")
        return None, None, None, None
