import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import re

@st.cache_data(ttl=86400)  # 24 óra cache
def scrape_co2_intensity():
    """
    Lekéri az éves átlagos CO2 intenzitást a lowcarbonpower.org oldalról.
    
    Returns:
        tuple: (co2_intensity (float), error_message (str or None))
    """
    # XPath az éves átlagos CO2 intenzitáshoz
    xpath_co2 = "/html/body/div[1]/div/main/div/div[2]/div[3]/span[1]"
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = None
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.get("https://lowcarbonpower.org/region/Hungary")
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)
        
        # CO2 intenzitás lekérése
        co2_element = driver.find_element(By.XPATH, xpath_co2)
        co2_text = co2_element.text
        
        print(f"Debug - CO2 intenzitás szöveg: {co2_text}")
        
        # Szám kinyerése a szövegből (pl. "207 gCO2eq/kWh" -> 207)
        # Távolítsuk el a "gCO2eq/kWh" részt és a szóközöket
        co2_match = re.search(r'(\d+(?:\.\d+)?)', co2_text)
        if co2_match:
            co2_intensity = float(co2_match.group(1))
            print(f"Debug - Kinyert CO2 intenzitás: {co2_intensity} gCO2eq/kWh")
            return co2_intensity, None
        else:
            return None, f"Nem sikerült kinyerni a CO2 intenzitást a szövegből: {co2_text}"
        
    except Exception as e:
        error_msg = f"Hiba a CO2 intenzitás lekérésekor: {str(e)}"
        print(f"Debug - {error_msg}")
        return None, error_msg
    
    finally:
        if driver:
            driver.quit()

