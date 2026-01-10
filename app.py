import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Black-Box", layout="wide")
st.title("🚗 Uber Schicht-Check & Black-Box")

uploaded_file = st.file_uploader("Uber Liste hochladen (Excel oder CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # 1. Datei laden
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python', on_bad_lines='skip')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Spalten festlegen
        fahrer_col = "Fahrername"
        start_col = "Uhrzeit des Fahrtbeginns"
        ende_col = "Uhrzeit des Fahrtendes"

        if fahrer_col not in df.columns or start_col not in df.columns:
            st.error(f"Spalten nicht gefunden. Gefunden: {list(df.columns)}")
        else:
            # Zeitformate umwandeln
            df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
            df[ende_col] = pd.to_datetime(df[ende_col], errors='coerce')
            df = df.dropna(subset=[fahrer_col, start_col])

            output = io.BytesIO()
            # HIER WAR DER FEHLER - Jetzt korrekt:
            orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for fahrer in df[fahrer_col].unique():
                    f_df = df[df[fahrer_col] == fahrer].sort_values(start_col).copy()
                    
                    # Pause berechnen
                    f_df['Pause_Minuten'] = (f_df[start_col] - f_df[ende_col].shift(1)).dt.total_seconds() / 60
                    
                    sheet_name = str(fahrer)[:30].replace("[", "").replace("]", "")
                    f_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    ws = writer.sheets[sheet_name]
                    for i, pause in enumerate(f_df['Pause_Minuten'], start=2):
                        if 0 <= pause < 5:
                            for cell in ws[i]:
                                cell.fill = orange_fill
            
            st.success(f"✅ Analyse fertig!")
            st.download_button("Download korrigierte Excel", data=output.getvalue(), file_name="Uber_Check_Ergebnis.xlsx")

    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
