import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel-Automator (Nur Abgeschlossen)", layout="wide")
st.title("🚗 Fahrtenbuch-Korrektur (Basis: Nur abgeschlossene Fahrten)")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    min_gap_to_fix = st.slider("Ab welcher Lücke (Min.) korrigieren?", 5, 60, 8)
    speed_kmh = st.number_input("Schnitt-KM/H für Anfahrt", value=22)
    st.markdown("---")
    st.warning("Hinweis: Stornierte Fahrten werden automatisch entfernt.")

uploaded_file = st.file_uploader("Rohdaten (test.xlsx) hochladen", type=["xlsx", "csv"])

ALLE_SPALTEN = [
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
        
        # Zeit-Parsing
        date_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
                     "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # --- DER FILTER: NUR GRÜNE (ABGESCHLOSSENE) FAHRTEN ---
        # Wir entfernen alles, was nicht 'abgeschlossen' ist
        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]
        
        # Zeilen ohne Zeit oder Kennzeichen löschen
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Kennzeichen"])

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for kennzeichen, group in df.groupby("Kennzeichen"):
                # Sortieren nach Zeit, damit die Kette stimmt
                group = group.sort_values("Uhrzeit des Fahrtbeginns")
                final_rows = []
                
                for i in range(len(group)):
                    row = group.iloc[i].to_dict()
                    row["_IS_CORRECTED"] = False
                    
                    if i > 0:
                        prev_ende = final_rows[i-1]["Uhrzeit des Fahrtendes"]
                        curr_start_orig = row["Uhrzeit des Fahrtbeginns"]
                        
                        # Lücke zum Vorgänger prüfen
                        gap = (curr_start_orig - prev_ende).total_seconds() / 60
                        
                        # Wenn die Lücke zu groß ist, ziehen wir sie zusammen
                        if gap > min_gap_to_fix:
                            # Realistische menschliche Kette bauen
                            pause = random.randint(2, 4)
                            zeit_nach_pause = prev_ende + timedelta(minutes=pause)
                            
                            # Auftragseingang
                            row["Datum/Uhrzeit Auftragseingang"] = zeit_nach_pause + timedelta(seconds=random.randint(10, 30))
                            row["Uhrzeit der Auftragsuebermittlung"] = row["Datum/Uhrzeit Auftragseingang"] + timedelta(seconds=15)
                            
                            # Neuer Fahrtbeginn (Anfahrt zum Kunden)
                            anfahrt_min = random.randint(3, 6)
                            new_start = row["Uhrzeit der Auftragsuebermittlung"] + timedelta(minutes=anfahrt_min)
                            
                            # Sicherstellen, dass wir nicht in die Zukunft springen
                            if new_start >= curr_start_orig:
                                new_start = curr_start_orig - timedelta(seconds=30)
                            
                            row["Uhrzeit des Fahrtbeginns"] = new_start
                            
                            # Kilometer für die gewonnene Zeit dazurechnen
                            zeit_gewinn = (curr_start_orig - new_start).total_seconds() / 60
                            extra_km = round(max(0, zeit_gewinn) * (speed_kmh / 60), 2)
                            
                            try:
                                row["Kilometer"] = round(float(row["Kilometer"]) + extra_km, 2)
                            except:
                                row["Kilometer"] = extra_km
                                
                            row["_IS_CORRECTED"] = True
                    
                    final_rows.append(row)

                # Export
                res_df = pd.DataFrame(final_rows)
                for col in date_cols:
                    if col in res_df.columns:
                        res_df[col] = pd.to_datetime(res_df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')

                sheet_name = str(kennzeichen)[:30]
                cols_to_export = [c for c in ALLE_SPALTEN if c in res_df.columns]
                res_df[cols_to_export].to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Styling
                ws = writer.sheets[sheet_name]
                for idx, r_data in enumerate(final_rows, start=2):
                    if r_data["_IS_CORRECTED"]:
                        for c_idx in range(1, len(cols_to_export) + 1):
                            ws.cell(row=idx, column=c_idx).fill = orange_fill

        st.success("✅ Fertig! Nur 'abgeschlossene' Fahrten wurden übernommen und optimiert.")
        st.download_button("Bereinigtes Taryel-Fahrtenbuch laden", data=output.getvalue(), file_name="Uber_Nur_Abgeschlossen.xlsx")
        
    except Exception as e:
        st.error(f"Fehler: {e}")
