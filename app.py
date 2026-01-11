import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Uber Smart-GPS", layout="wide")
st.title("🚗 Uber Fahrtenbuch mit GPS-Positions-Berechnung")

with st.sidebar:
    st.header("🏢 Betriebssitz Daten")
    str_hnr = st.text_input("Straße & Hausnummer", "Falderstraße 3")
    plz = st.text_input("PLZ", "50999")
    ort = st.text_input("Ort", "Köln")
    # Wichtig: Diese Start-Koordinaten brauchen wir als Anker
    bs_coords = st.text_input("GPS-Koordinaten Betriebssitz (Lat Lon)", "50.8800 6.9900")
    st.info("Logik: Fahrzeug bewegt sich mit 50 km/h Richtung Betriebssitz. Bei neuem Auftrag wird die exakte GPS-Position auf dem Weg berechnet.")

def calculate_intermediate_coords(start_coords_str, target_coords_str, minutes_passed, speed_kmh=50):
    try:
        # Umwandlung der Strings in Zahlen
        lat1, lon1 = map(float, start_coords_str.split())
        lat2, lon2 = map(float, target_coords_str.split())
        
        # Distanz, die in den Minuten geschafft wurde (50 km/h = 0.833 km pro Min)
        distance_km = minutes_passed * (speed_kmh / 60)
        
        # Grobe Schätzung der Gesamtentfernung (vereinfacht für Performance)
        total_dist = ((lat2-lat1)**2 + (lon2-lon1)**2)**0.5 * 111 # 1 Grad ~ 111km
        
        if total_dist == 0 or distance_km >= total_dist:
            return target_coords_str # Er ist schon am Ziel
        
        # Berechnung des Punktes auf der Linie (Verhältnis)
        ratio = distance_km / total_dist
        new_lat = lat1 + (lat2 - lat1) * ratio
        new_lon = lon1 + (lon2 - lon1) * ratio
        
        return f"{round(new_lat, 6)} {round(new_lon, 6)}"
    except:
        return start_coords_str

# ... (Restliche Datenverarbeitung bleibt gleich, hier die Logik-Anpassung) ...
# Im Loop der Leerfahrten:
# leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = calculate_intermediate_coords(
#     vorherige_fahrt["Standort_Ende"], # Wir müssten hier die GPS des Zielorts haben
#     bs_coords, 
#     pause_min
# )
