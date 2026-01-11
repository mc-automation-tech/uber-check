import streamlit as st
import pandas as pd
import io
import math
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-GPS Pro", layout="wide")
st.title("🚗 Uber Fahrtenbuch: Getrennte Auswertung pro Fahrer")

# --- SIDEBAR: KONFIGURATION ---
with st.sidebar:
    st.header("🏢 Betriebssitz Daten")
    strasse = st.text_input("Straße", "Falderstraße")
    hausnummer = st.text_input("Hausnummer", "3")
    plz = st.text_input("PLZ", "50999")
    ort = st.text_input("Ort", "Köln")
    bs_coords = st.text_input("GPS Betriebssitz (z.B. 50.8800 6.9900)", "50.885277 6.9877386")
    
    st.markdown("---")
    speed_kmh = st.number_input("Durchschnitts-KM/H für Leerfahrt", value=50)
    st.info("Das Programm erstellt für jeden Fahrer ein eigenes Blatt in der Excel-Datei.")

full_bs_address = f"{strasse} {hausnummer}, {plz} {ort}"

def calculate_current_gps(start_gps_str, target_gps_str, minutes, speed):
    """Berechnet die GPS-Position zwischen zwei Punkten nach X Minuten."""
    try:
        s_lat, s_lon = map(float, str(start_gps_str).split())
        t_lat, t_lon = map(float, str(target_gps_str).split())
        
        dist_traveled = minutes * (speed / 60)
        deg_dist = math.sqrt((t_lat - s_lat)**2 + (t_lon - s_lon)**2)
        km_dist = deg_dist * 111 
        
        if km_dist == 0 or dist_traveled >= km_dist:
            return target_gps_str
        
        ratio = dist_traveled / km_dist
        new_lat = s_lat + (t_lat - s_lat) * ratio
        new_lon = s_lon + (t_lon - s_lon) * ratio
        return f"{round(new_lat, 6)} {round(new_lon, 6)}"
    except:
        return start_gps_str

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

WUNSCH_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt",
    "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns",
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername",
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Datei einlesen
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).strip() for c in df.columns]

        # Spalten für Zeiten konvertieren
        time_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
                     "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
        for col in time_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
        
        # Excel-Erstellung
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Gruppen nach Fahrername
            for fahrer, group in df.groupby("Fahrername"):
                f_df = group.sort_values("Uhrzeit des Fahrtbeginns").copy()
                neue_zeilen = []
                
                for i in range(len(f_df)):
                    aktuelle_fahrt = f_df.iloc[i]
                    
                    # Logik für Pausen zwischen Fahrten
                    if i > 0:
                        vorherige_fahrt = f_df.iloc[i-1]
                        # Pause zwischen Ende alter Fahrt und Eingang neuer Auftrag
                        pause_min = (aktuelle_fahrt["Datum/Uhrzeit Auftragseingang"] - vorherige_fahrt["Uhrzeit des Fahrtendes"]).total_seconds() / 60
                        
                        if pause_min > 5:
                            leer = {c: "" for c in WUNSCH_SPALTEN}
                            leer["Fahrername"] = fahrer
                            leer["Datum der Fahrt"] = aktuelle_fahrt["Uhrzeit des Fahrtbeginns"].strftime('%Y-%m-%d')
                            leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt["Uhrzeit des Fahrtendes"].strftime('%Y-%m-%d %H:%M:%S')
                            leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt["Datum/Uhrzeit Auftragseingang"].strftime('%Y-%m-%d %H:%M:%S')
                            leer["Abholort"] = vorherige_fahrt["Zielort"]
                            leer["Kilometer"] = round(pause_min * (
