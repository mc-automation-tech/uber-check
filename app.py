import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Black-Box", layout="wide")
st.title("🚗 Uber Fahrtenbuch & Rückfahrt-Check")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

# Die von dir gewünschten 13 Spalten
WUNSCH_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt",
    "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns",
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
        
        # Nur vorhandene Wunsch-Spalten behalten
        df = df[[c for c in WUNSCH_SPALTEN if c in df.columns]]
        
        # Zeit-Umwandlung
        start_col = "Uhrzeit des Fahrtbeginns"
        ende_col = "Uhrzeit des Fahrtendes"
        df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
        df[ende_col] = pd.to_datetime(df[ende_col], errors='coerce')

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for fahrer in df["Fahrername"].unique():
                f_df = df[df["Fahrername"] == fahrer].sort_values(start_col).copy()
                
                # Neue Liste für Zeilen (inkl. Leerfahrten)
                neue_zeilen = []
                
                for i in range(len(f_df)):
                    aktuelle_fahrt = f_df.iloc[i]
                    
                    # Prüfen, ob eine Leerfahrt dazwischen muss
                    if i > 0:
                        vorherige_fahrt = f_df.iloc[i-1]
                        pause = (aktuelle_fahrt[start_col] - vorherige_fahrt[ende_col]).total_seconds() / 60
                        
                        if pause > 5:
                            # Leerfahrt-Zeile generieren
                            leerfahrt = {c: "" for c in WUNSCH_SPALTEN}
                            leerfahrt["Fahrername"] = fahrer
                            leerfahrt["Datum der Fahrt"] = aktuelle_fahrt["Datum der Fahrt"]
                            leerfahrt["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt[ende_col]
                            leerfahrt["Uhrzeit des Fahrtendes"] = aktuelle_fahrt[start_col]
                            leerfahrt["Abholort"] = vorherige_fahrt["Zielort"]
                            leerfahrt["Zielort"] = "Betriebssitz (Rückfahrtpflicht)"
                            leerfahrt["Fahrtstatus"] = "LEERFAHRT" # Markierung intern
                            neue_zeilen.append(leerfahrt)
                    
                    neue_zeilen.append(aktuelle_fahrt.to_dict())
                
                final_df = pd.DataFrame(neue_zeilen)
                
                # Zeiten für Excel wieder hübsch machen
                for col in [start_col, ende_col]:
                    final_df[col] = final_df[col].dt.strftime('%d.%m.%Y %H:%M:%S')
                
                sheet_name = str(fahrer)[:30]
                final_df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Orange Markierung für die Leerfahrt-Zeilen
                ws = writer.sheets[sheet_name]
                for row_idx, row in enumerate(neue_zeilen, start=2):
                    if row.get("Fahrtstatus") == "LEERFAHRT":
                        for cell in ws[row_idx]:
                            cell.fill = orange_fill
                            
        st.success("✅ Fertig! Leerfahrten wurden zwischengefügt und Spalten gefiltert.")
        st.download_button("Download saubere Liste", data=output.getvalue(), file_name="Uber_Check_Final.xlsx")

    except Exception as e:
        st.error(f"Fehler: {e}")
