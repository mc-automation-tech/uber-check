import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel Ultimate Logic", layout="wide")

st.title("🚗 Taryel-Logik: Realistische Schichten & Standorte")
st.markdown("Dieses Skript bereinigt \N, simuliert Standorte und glättet die Fahrtenfolge.")

with st.sidebar:
    st.header("⚙️ Konfiguration")
    speed_city = st.number_input("Schnitt KM/H für Anfahrt", value=22)
    min_pause = st.slider("Pause zw. Fahrten (Min)", 2, 5, 3)

uploaded_file = st.file_uploader("Rohdaten hochladen", type=["xlsx", "csv"])

FINAL_COLUMNS = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Einlesen
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]

        # 1. Nur abgeschlossene Fahrten
        df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]
        
        # 2. Zeit-Parsing & \N Korrektur
        date_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Kennzeichen"])

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df['Tag_Key'] = df['Uhrzeit des Fahrtbeginns'].dt.date
            
            for (tag, kennzeichen, fahrer), group in df.groupby(['Tag_Key', 'Kennzeichen', 'Fahrername']):
                group = group.sort_values("Uhrzeit des Fahrtbeginns")
                final_rows = []
                
                # Wir merken uns die letzte Position (Koordinaten)
                # Falls leer, nehmen wir Kölner Zentrum als Start
                last_coords = "50.9375 6.9603" 

                for i in range(len(group)):
                    row = group.iloc[i].to_dict()
                    
                    # Logik: Ist
