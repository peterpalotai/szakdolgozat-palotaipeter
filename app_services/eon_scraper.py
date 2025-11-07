import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

@st.cache_data(ttl=2600000) 
def scrape_eon_prices():
    
    # XPath for the veszteségi ár
    xpath1 = "/html/body/eon-ui-page-wrapper/main/div/eon-ui-section/eon-ui-grid-control/eon-ui-grid-control-column/eon-ui-grid-control/eon-ui-grid-control-column[1]/div[4]/table/tbody/tr[19]/td[3]"
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    driver = None
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
     
        driver.get("https://www.eon.hu/hu/lakossagi/aram/arak.html")
        
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)
        
       
        value1 = driver.find_element(By.XPATH, xpath1).text
        
       
        print(f"Debug - Veszteségi ár: {value1}")
        
        return value1, None
        
    except Exception as e:
        return None, str(e)
    
    finally:
        if driver:
            driver.quit()

def calculate_energy_costs(consumption_data, loss_price):
    """Számítja az energia költségeket a fogyasztás alapján
    
    Args:
        consumption_data: Napi átlagos fogyasztás Watt-ban (W)
        loss_price: Veszteségi energiaár (Ft/kWh)
    
    Returns:
        tuple: (veszteségi_költség, veszteségi_ár)
    """
    try:
        
        loss_price_num = float(loss_price.replace(',', '.').replace(' Ft/kWh', ''))
        
        #Napi átlagos fogyasztás konvertálása kWh-ba
        daily_consumption_kwh = (consumption_data / 1000) * 24
        
        #Napi költség számítása
        daily_loss_cost = daily_consumption_kwh * loss_price_num
        
        return daily_loss_cost, loss_price_num
    except Exception as e:
        st.error(f"Hiba a költségek számításakor: {e}")
        return None, None
