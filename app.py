import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-Logik", layout="wide")
st.title("🚗 Uber Fahrtenbuch-Optimierer")

# --- SIDEBAR KONFIGURATION ---
with st.sidebar:
    st.header("Konfiguration")
    betriebssitz = st.text_input("Adresse/Koordinaten Betriebssitz", "Musterstraße 1, 12345 Stadt")
    st.info("Grün = Lückenschluss (kleine Pause)\nOrange = Rückfahrtpflicht (große Pause)")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

WUNSCH_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt",
    "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns",
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername",
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]

        start_col, ende_col, eingang_col = "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang"
        for col in [start_col, ende_col, eingang_col]:
            df[col] = pd.to_datetime(df[col], errors='coerce')

        output = io.BytesIO()
        # Farben definieren
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for fahrer in df["Fahrername"].unique():
                f_df = df[df["Fahrername"] == fahrer].sort_values(start_col).copy()
                neue_zeilen = []
                
                for i in range(len(f_df)):
                    aktuelle_fahrt = f_df.iloc[i]
                    if i > 0:
                        vorherige_fahrt = f_df.iloc[i-1]
                        pause_min = (aktuelle_fahrt[eingang_col] - vorherige_fahrt[ende_col]).total_seconds() / 60
                        
                        # FALL 1: Kleine Lücke (5 - 15 Min) -> GRÜN (Anschlussfahrt simuliert)
                        if 5 < pause_min <= 15:
                            leer = {c: "" for c in WUNSCH_SPALTEN}
                            leer["Fahrername"] = fahrer
                            leer["Datum der Fahrt"] = aktuelle_fahrt[start_col].strftime('%Y-%m-%d')
                            leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt[ende_col].strftime('%Y-%m-%d %H:%M:%S')
                            leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt[eingang_col].strftime('%Y-%m-%d %H:%M:%S')
                            leer["Abholort"] = vorherige_fahrt["Zielort"]
                            leer["Zielort"] = aktuelle_fahrt["Abholort"]
                            leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = "Bereitstellung (Anschluss)"
                            leer["_COLOR"] = "GREEN"
                            neue_zeilen.append(leer)
                            
                        # FALL 2: Große Lücke (> 15 Min) -> ORANGE (Rückfahrtpflicht)
                        elif pause_min > 15:
                            leer = {c: "" for c in WUNSCH_SPALTEN}
                            leer["Fahrername"] = fahrer
                            leer["Datum der Fahrt"] = aktuelle_fahrt[start_col].strftime('%Y-%m-%d')
                            leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt
