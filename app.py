import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Black-Box", layout="wide")
st.title("🚗 Uber Schicht-Check & Black-Box")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # 1. Datei laden mit automatischer Trenner-Erkennung
        if uploaded_file.name.endswith('.csv'):
            # 'sep=None' lässt Python raten, ob Komma oder Semikolon genutzt wird
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        # 2. Spaltennamen extrem gründlich säubern
        df.columns = [str(c).strip() for c in df.columns]
        
        # 3. Spalten suchen (wir suchen nach Begriffen, falls sie leicht anders heißen)
        fahrer_col = next((c for c in df.columns if "Fahrername" in c or "Driver" in c), None)
        start_col = next((c for c in df.columns if "Fahrtbeginns" in c or "Startzeit" in c), None)
        ende_col = next((c for c in df.columns if "Fahrtendes" in c or "Endzeit" in c), None)

        if not fahrer_col or not start_col or not ende_col:
            st.error(f"Konnte Spalten nicht finden. Gefunden wurden: {list(df.columns)}")
        else:
            # 4. Zeit-Umwandlung (wichtig für die Berechnung)
            df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
            df[ende_col] = pd.to_datetime(df[ende_col], errors='coerce')

            output = io.BytesIO()
            orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid
