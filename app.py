import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Schicht-Master Pro", layout="wide")

# --- UI MASKE ---
st.title("🚗 Taryel-Logik: Der Schicht-Generator")
st.markdown("Erstellt aus der Rohliste eine saubere, grüne Auswertung inkl. Pausen.")

with st.sidebar:
    st.header("🏢 Stammdaten")
    betriebssitz = st.text_input("Betriebssitz (Start/Ende)", "Otto-Klein-Straße 24, 50858 Köln")
    st.header("⚙️ Parameter")
    speed_city = st.number_input("Schnitt KM/H für Anfahrten", value=22)
    pause_min = st.slider("Gesetzliche Pause (Min)", 30, 60, 45)

uploaded_file = st.file_uploader("test.xlsx hochladen", type=["xlsx", "csv"])

# Spalten-Definition für das grüne Ergebnis (Taryel-Style)
FINAL_COLUMNS = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Einlesen der Datei
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Spaltennamen säubern
        df.columns = [str(c).strip() for c in df.columns]

        # 1. SCHRITT: NUR DIE GRÜNEN (ABGESCHLOSSEN)
        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]

        # 2. SCHRITT: DATUMSKORREKTUR (Löst das \N Problem)
        date_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
                     "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
        
        for col in date_cols:
            if
