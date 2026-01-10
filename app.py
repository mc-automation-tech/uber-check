import streamlit as st
import pandas as pd
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Black-Box", layout="wide")
st.title("🚗 Uber Schicht-Check & Black-Box")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

if uploaded_file:
    df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
    df.columns = [c.strip() for c in df.columns]

    # Automatische Spaltensuche (falls Uber die Namen ändert)
    fahrer_col = next((c for c in df.columns if "Fahrer" in c), None)
    zeit_col = next((c for c in df.columns if "Uhrzeit des Fahrtbeginns" in c or "Startzeit" in c), None)

    if not fahrer_col or not zeit_col:
        st.error(f"Spalten nicht gefunden. Vorhanden sind: {list(df.columns)}")
    else:
        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for fahrer in df[fahrer_col].unique():
                f_df = df[df[fahrer_col] == fahrer].copy()
                f_df[zeit_col] = pd.to_datetime(f_df[zeit_col])
                f_df = f_df.sort_values(zeit_col)

                # Zeitdifferenz berechnen (in Minuten zum Vorjahr)
                f_df['Differenz_Min'] = f_df[zeit_col].diff().dt.total_seconds() / 60
                
                sheet_name = str(fahrer)[:31].replace("[", "").replace("]", "")
                f_df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Orange Markierung für verdächtige Fahrten (< 5 Min Pause)
                worksheet = writer.sheets[sheet_name]
                for i, diff in enumerate(f_df['Differenz_Min'], start=2):
                    if diff < 5:  # HIER: Grenze in Minuten einstellen
                        for cell in worksheet[i]:
                            cell.fill = orange_fill

        st.success("Analyse fertig! Verdächtige Fahrten (< 5 Min Pause) sind orange markiert.")
        st.download_button("Datei herunterladen", data=output.getvalue(), file_name="Uber_Check_Markiert.xlsx")
