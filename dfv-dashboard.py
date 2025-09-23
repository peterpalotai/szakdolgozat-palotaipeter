import streamlit as st
from database import get_db_connection, test_db_connection, execute_query

st.write("# DFV Dashboard")
st.write("This is your Streamlit dashboard")

# Database connection test
if st.button("Adatbázis teszt"):
    if test_db_connection():
        st.success("Sikeres csatlakozás")
    else:
        st.error("Sikertelen csatlakozás")

# Example database usage
st.write("## Adatbázis műveletek")


try:
    db = get_db_connection()
    

    if st.button("Példa lekérdezés"):
        result = execute_query("SELECT trend_para_smart_i1 FROM dfv_smart_db WHERE trend_para_smart_i1 = 0.18767")
        if result:
            st.write("i1-es vonali feszültség:", result[0][0])
        else:
            st.write("Nem tért vissza érték")
            
except Exception as e:
    st.error(f"Adatbázishiba: {e}")