import streamlit as st
import pandas as pd
import io
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel-Logik Automator", layout="wide")
st.title("🚗 Automatisierte Fahrtenbuch-Korrektur")

with st.sidebar:
    st.header("⚙️ Analyse-Parameter")
    # Taryel korrigiert meistens Lücken, die länger als eine kurze Kaffeepause sind
    min_gap = st.slider("Ab welcher Lücke (Min.) soll korrigiert werden?", 2, 60, 5)
    speed_kmh = st.number_input("Schnitt-KM/H für Anfahrt-Korrektur", value=25)
    st.write("Das Programm zieht die Startzeit zurück und markiert die Zeile orange – exakt wie in der Vorlage.")

uploaded_file = st.file_uploader("Rohdaten (test.xlsx) hochladen", type=["xlsx", "csv"])

# Die exakte Struktur aus der Taryel-Datei
COLUMNS_TO_KEEP = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
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
        
        # Zeit-Parsing (wichtig für die Berechnung)
        df["Uhrzeit des Fahrtbeginns"] = pd.to_datetime(df["Uhrzeit des Fahrtbeginns"], errors='coerce')
        df["Uhrzeit des Fahrtendes"] = pd.to_datetime(df["Uhrzeit des Fahrtendes"], errors='coerce')
        
        # Nur abgeschlossene Fahrten wie bei Taryel
        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.contains("abgeschlossen", case=False, na=False)]
        
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Kennzeichen"])

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for kennzeichen, group in df.groupby("Kennzeichen"):
                group = group.sort_values("Uhrzeit des Fahrtbeginns")
                processed_rows = []
                
                for i in range(len(group)):
                    row = group.iloc[i].to_dict()
                    row["_CORRECTED"] = False
                    
                    if i > 0:
                        prev_ende = processed_rows[i-1]["Uhrzeit des Fahrtendes"]
                        curr_start = row["Uhrzeit des Fahrtbeginns"]
                        
                        # Berechnung der Lücke
                        gap_duration = (curr_start - prev_ende).total_seconds() / 60
                        
                        # Wenn die Lücke größer als das Limit ist -> Zeit zurückziehen (Taryel-Logik)
                        if gap_duration > min_gap:
                            # 1. Startzeit auf Ende der Vorfahrt setzen
                            row["Uhrzeit des Fahrtbeginns"] = prev_ende
                            
                            # 2. Kilometer anpassen (Anfahrt-KM hinzufügen)
                            extra_km = round(gap_duration * (speed_kmh / 60), 2)
                            try:
                                row["Kilometer"] = round(float(row["Kilometer"]) + extra_km, 2)
                            except:
                                row["Kilometer"] = extra_km
                                
                            row["_CORRECTED"] = True
                    
                    processed_rows.append(row)

                # Zurück in DataFrame
                res_df = pd.DataFrame(processed_rows)
                
                # Zeit-Formatierung für die finale Excel
                for col in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]:
                    if col in res_df.columns:
                        res_df[col] = pd.to_datetime(res_df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')

                sheet_name = str(kennzeichen)[:30].replace(":", "")
                # Nur die relevanten Spalten exportieren
                final_cols = [c for c in COLUMNS_TO_KEEP if c in res_df.columns]
                res_df[final_cols].to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Farbe setzen
                ws = writer.sheets[sheet_name]
                for idx, r_data in enumerate(processed_rows, start=2):
                    if r_data["_CORRECTED"]:
                        for c_idx in range(1, len(final_cols) + 1):
                            ws.cell(row=idx, column=c_idx).fill = orange_fill

        st.success("✅ Taryel-Logik erfolgreich angewendet!")
        st.download_button("Manuell korrigierte Version (automatisch erstellt) laden", data=output.getvalue(), file_name="Taryel_Style_Korrektur.xlsx")
        
    except Exception as e:
        st.error(f"Fehler: {e}")
