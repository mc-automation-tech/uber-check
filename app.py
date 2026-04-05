import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel-Automator Pro", layout="wide")
st.title("🚗 Taryel-Logik: Realistische Zeitabstände")

with st.sidebar:
    st.header("⚙️ Realitäts-Parameter")
    min_gap_to_fix = st.slider("Ab welcher Lücke (Min.) korrigieren?", 5, 60, 10)
    buffer_min = st.slider("Mindest-Pause zwischen Fahrten (Min.)", 1, 5, 2)
    speed_kmh = st.number_input("Schnitt-KM/H für Anfahrt", value=22)
    st.info("Das Programm lässt nun eine kleine Lücke (Puffer), damit es menschlich aussieht.")

uploaded_file = st.file_uploader("Datei hochladen (test.xlsx)", type=["xlsx", "csv"])

ALLE_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).strip() for c in df.columns]
        
        # Zeit-Korrektur (Fehlerbehebung für \N)
        for col in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
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
                        
                        # Aktuelle Lücke
                        gap = (curr_start - prev_ende).total_seconds() / 60
                        
                        if gap > min_gap_to_fix:
                            # Wir lassen einen zufälligen Puffer zwischen 2 und 5 Minuten
                            puffer = random.randint(buffer_min, buffer_min + 3)
                            new_start = prev_ende + timedelta(minutes=puffer)
                            
                            # Neue Zeiten setzen
                            row["Uhrzeit des Fahrtbeginns"] = new_start
                            # Auftragseingang muss kurz VOR Fahrtbeginn sein
                            row["Datum/Uhrzeit Auftragseingang"] = new_start - timedelta(minutes=random.randint(1, 3))
                            row["Uhrzeit der Auftragsuebermittlung"] = row["Datum/Uhrzeit Auftragseingang"] + timedelta(seconds=15)
                            
                            # Kilometer für die Zeitüberbrückung (minus Pufferzeit)
                            fahrt_zeit_diff = (curr_start - new_start).total_seconds() / 60
                            extra_km = round(max(0, fahrt_zeit_diff) * (speed_kmh / 60), 2)
                            
                            try:
                                row["Kilometer"] = round(float(row["Kilometer"]) + extra_km, 2)
                            except:
                                row["Kilometer"] = extra_km
                                
                            row["_IS_CORRECTED"] = True
                    
                    final_rows.append(row)

                res_df = pd.DataFrame(final_rows)
                
                # Formatierung für Excel
                date_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
                for col in date_cols:
                    if col in res_df.columns:
                        res_df[col] = pd.to_datetime(res_df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')

                sheet_name = str(kennzeichen)[:30]
                cols_to_export = [c for c in ALLE_SPALTEN if c in res_df.columns]
                res_df[cols_to_export].to_excel(writer, sheet_name=sheet_name, index=False)
                
                ws = writer.sheets[sheet_name]
                for idx, r_data in enumerate(final_rows, start=2):
                    if r_data["_IS_CORRECTED"]:
                        for c_idx in range(1, len(cols_to_export) + 1):
                            ws.cell(row=idx, column=c_idx).fill = orange_fill

        st.success("✅ Realistische Zeitabstände eingebaut (2-5 Min. Puffer).")
        st.download_button("Optimierte Datei laden", data=output.getvalue(), file_name="Uber_Korrektur_Menschlich.xlsx")
        
    except Exception as e:
        st.error(f"Fehler: {e}")
