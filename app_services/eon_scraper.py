import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

"""Chrome driver beállítása."""
def _setup_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

"""Ár lekérése az adott XPath alapján."""
def _scrape_price(driver, xpath):
    try:
        element = driver.find_element(By.XPATH, xpath)
        return element.text
    except Exception as e:
        st.error(f"Hiba az ár lekérésekor ({xpath}): {e}")
        return None

"""Várakozás az oldal betöltésére."""
def _wait_for_page_load(driver):
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(3)


@st.cache_data(ttl=2600000)
def scrape_eon_prices():
    """Lekéri az E.ON veszteségi árait 2024-re és 2025-re."""
    xpath_2024 = "/html/body/eon-ui-page-wrapper/main/div/eon-ui-section/eon-ui-grid-control/eon-ui-grid-control-column/eon-ui-grid-control/eon-ui-grid-control-column[1]/div[4]/table/tbody/tr[18]/td[3]"
    xpath_2025 = "/html/body/eon-ui-page-wrapper/main/div/eon-ui-section/eon-ui-grid-control/eon-ui-grid-control-column/eon-ui-grid-control/eon-ui-grid-control-column[1]/div[4]/table/tbody/tr[19]/td[3]"
    
    driver = None
    try:
        driver = _setup_chrome_driver()
        driver.get("https://www.eon.hu/hu/lakossagi/aram/arak.html")
        _wait_for_page_load(driver)
        
        value_2024 = _scrape_price(driver, xpath_2024)
        value_2025 = _scrape_price(driver, xpath_2025)
        
        if value_2024 and value_2025:
            return {
                '2024': value_2024,
                '2025': value_2025
            }, None
        else:
            return None, "Nem sikerült lekérni az árakat"
            
    except Exception as e:
        return None, str(e)
    finally:
        if driver:
            driver.quit()

"""Ár string konvertálása float-ra."""
def _parse_price(price_str):
    try:
        return float(price_str.replace(',', '.').replace(' Ft/kWh', ''))
    except Exception as e:
        st.error(f"Hiba az ár feldolgozásakor: {e}")
        return None

"""Energia költségek számítása a fogyasztás alapján."""
def calculate_energy_costs(consumption_data, loss_price):
    try:
        loss_price_num = _parse_price(loss_price)
        if loss_price_num is None:
            return None, None
        
        daily_consumption_kwh = (consumption_data / 1000) * 24
        daily_loss_cost = daily_consumption_kwh * loss_price_num
        
        return daily_loss_cost, loss_price_num
    except Exception as e:
        st.error(f"Hiba a költségek számításakor: {e}")
        return None, None
