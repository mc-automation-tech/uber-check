import streamlit as st
import pandas as pd
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Schicht-Check", layout="wide")
st.title("🚗 Uber Fahrtenbuch Black-Box")
st.write("Lade deine Uber-Liste hoch, um fahrerbezogene Auswertungen zu erhalten.")

uploaded_file = st.file_uploader("Uber Excel- oder CSV-Datei wählen", type=["xlsx", "csv"])

if uploaded_file:
    # Daten laden
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Spaltennamen säubern
    df.columns = [c.strip() for c in df.columns]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Jeden Fahrer in ein eigenes Tabellenblatt
        for fahrer in df['Fahrername'].unique():
            f_df = df[df['Fahrername'] == fahrer].copy()
            f_df['Uhrzeit des Fahrtbeginns'] = pd.to_datetime(f_df['Uhrzeit des Fahrtbeginns'])
            f_df = f_df.sort_values('Uhrzeit des Fahrtbeginns')
            
            # Zeit wieder lesbar machen für Excel
            f_df['Uhrzeit des Fahrtbeginns'] = f_df['Uhrzeit des Fahrtbeginns'].dt.strftime('%d.%m.%Y %H:%M')
            
            # Tabellenblatt erstellen (Name max 31 Zeichen)
            sheet_name = str(fahrer)[:31]
            f_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
    st.success("Analyse abgeschlossen!")
    st.download_button("Korigierte Excel herunterladen", data=output.getvalue(), file_name="Uber_Check_Ergebnis.xlsx")
