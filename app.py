import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel Logic Pro", layout="wide")

# --- UI ---
st.title("🚗 Taryel-Logik: Schichten & Standorte")
st.markdown(r"Bereinigt \N, simuliert Standorte und schließt Lücken.")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    speed_city = st.number_input("Schnitt KM/H", value=22)
    min_p = st.slider("Pause zw. Fahrten (Min)", 2, 5, 3)

uploaded_file = st.file_uploader("Rohdaten hochladen", type=["xlsx", "csv"])

# Spalten-Definition
FINAL_COLS = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", 
    "Datum der Fahrt", "Fahrtstatus", 
    "Standort des Fahrzeugs bei Auftragsuebermittlung", 
    "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
    "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Einlesen
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
            
        df.columns = [str(c).strip() for c in df.columns]

        # 1. Nur abgeschlossene
        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]
        
        # 2. Zeit-Parsing
        d_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
                  "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
        for col in d_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Kennzeichen"])

        if not df.empty:
            output = io.BytesIO()
            orange = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df['Tag_Key'] = df['Uhrzeit des Fahrtbeginns'].dt.date
                
                for (tag, kennz, fahrer), group in df.groupby(['Tag_Key', 'Kennzeichen', 'Fahrername']):
                    group = group.sort_values("Uhrzeit des Fahrtbeginns")
                    rows = []
                    # Standard Köln Koordinate
                    last_loc = "50.9375 6.9603" 

                    for i in range(len(group)):
                        row = group.iloc[i].to_dict()
                        
                        # Standort-Spaltenname in Variable für Kürze
                        loc
