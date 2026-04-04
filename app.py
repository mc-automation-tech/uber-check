import streamlit as st
import pandas as pd
import io
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel-Automator v2", layout="wide")
st.title("🚗 Taryel-Logik: Automatisierte Korrektur")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    min_gap = st.slider("Ab welcher Lücke (Min.) korrigieren?", 2, 60, 5)
    speed_kmh = st.number_input("Schnitt-KM/H für Anfahrt", value=25)
    st.info("Dieser Code ignoriert '\\N' Werte und markiert Korrekturen orange.")

uploaded_file = st.file_uploader("Datei hochladen (test.xlsx)", type=["xlsx", "csv"])

# Die exakten Spalten aus deiner Liste
ALLE_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # 1. Einlesen
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Zeit-Korrektur (WICHTIG: Fehlerbehebung für \N)
        for col in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes"]:
            if col in df.columns:
                # errors='coerce' macht aus \N ein 'NaT' (Not a Time), was wir später filtern
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Nur abgeschlossene Fahrten mit gültigen Zeiten
        df = df[df["Fahrtstatus"].str.contains("abgeschlossen", case=False, na=False)]
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Kennzeichen"])

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for kennzeichen, group in df.groupby("Kennzeichen"):
                group = group.sort_values("Uhrzeit des Fahrtbeginns")
                final_rows = []
                
                for i in range(len(group)):
                    row = group.iloc[i].to_dict()
                    row["_IS_CORRECTED"] = False
                    
                    if i > 0:
                        prev_ende = final_rows[i-1]["Uhrzeit des Fahrtendes"]
                        curr_start = row["Uhrzeit des Fahrtbeginns"]
                        
                        # Lücke in Minuten berechnen
                        gap = (curr_start - prev_ende).total_seconds() / 60
                        
                        # Taryel-Logik: Zeit zurückziehen wenn Lücke zu groß
                        if gap > min_gap:
                            row["Uhrzeit des Fahrtbeginns"] = prev_ende
                            # Kilometer für die Zeitüberbrückung dazurechnen
                            extra_km = round(gap * (speed_kmh / 60), 2)
                            try:
                                row["Kilometer"] = round(float(row["Kilometer"]) + extra_km, 2)
                            except:
                                row["Kilometer"] = extra_km
                            row["_IS_CORRECTED"] = True
                    
                    final_rows.append(row)

                # Zurück in DataFrame
                res_df = pd.DataFrame(final_rows)
                
                # Formatierung für Excel (Datum zurück zu String ohne Millisekunden)
                for col in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes"]:
                    res_df[col] = res_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')

                sheet_name = str(kennzeichen)[:30]
                # Nur gewünschte Spalten exportieren
                cols_to_export = [c for c in ALLE_SPALTEN if c in res_df.columns]
                res_df[cols_to_export].to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Farbe setzen
                ws = writer.sheets[sheet_name]
                for idx, r_data in enumerate(final_rows, start=2):
                    if r_data["_IS_CORRECTED"]:
                        for c_idx in range(1, len(cols_to_export) + 1):
                            ws.cell(row=idx, column=c_idx).fill = orange_fill

        st.success("✅ Erledigt! '\\N' Fehler abgefangen und Lücken geschlossen.")
        st.download_button("Optimierte Datei laden", data=output.getvalue(), file_name="Uber_Korrektur_Final.xlsx")
        
    except Exception as e:
        st.error(f"Kritischer Fehler: {e}")
