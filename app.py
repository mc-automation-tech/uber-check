import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

# --- KONFIGURATION DEINES BETRIEBSSITZES ---
# Hier deine echten Geschäftsstellen-Koordinaten eintragen:
KOORDINATEN_BETRIEBSSITZ = "50.9333 6.9500" 

st.set_page_config(page_title="Uber Smart-Check", layout="wide")
st.title("🚗 Uber Intelligente Rückfahrt-Logik")

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

        # Zeit-Umwandlung
        start_col = "Uhrzeit des Fahrtbeginns"
        ende_col = "Uhrzeit des Fahrtendes"
        eingang_col = "Datum/Uhrzeit Auftragseingang"
        ueber_col = "Uhrzeit der Auftragsuebermittlung"
        
        for col in [start_col, ende_col, eingang_col, ueber_col]:
            df[col] = pd.to_datetime(df[col], errors='coerce')

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for fahrer in df["Fahrername"].unique():
                f_df = df[df["Fahrername"] == fahrer].sort_values(start_col).copy()
                neue_zeilen = []
                
                for i in range(len(f_df)):
                    aktuelle_fahrt = f_df.iloc[i]
                    
                    if i > 0:
                        vorherige_fahrt = f_df.iloc[i-1]
                        pause = (aktuelle_fahrt[eingang_col] - vorherige_fahrt[ende_col]).total_seconds() / 60
                        
                        # Nur wenn Pause > 5 Minuten, wird eine Leerfahrt-Zeile fällig
                        if pause > 5:
                            leer = {c: "" for c in WUNSCH_SPALTEN}
                            leer["Fahrername"] = fahrer
                            leer["Datum der Fahrt"] = aktuelle_fahrt[start_col].strftime('%Y-%m-%d')
                            leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt[ende_col]
                            leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt[eingang_col]
                            leer["Abholort"] = vorherige_fahrt["Zielort"]
                            leer["Zielort"] = "Rückfahrt Betriebssitz"
                            
                            # Logik für Koordinaten-Berechnung
                            # Annahme: Rückfahrt dauert 30 Min.
                            if pause >= 30:
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = KOORDINATEN_BETRIEBSSITZ
                            else:
                                # Errechnet einen fiktiven Wendepunkt zwischen altem Ziel und Betriebssitz
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = "Wendepunkt (Rückweg)"
                            
                            leer["STATUS_INTERN"] = "ORANGE"
                            neue_zeilen.append(leer)
                    
                    # Aktuelle Fahrt hinzufügen
                    f_dict = aktuelle_fahrt.to_dict()
                    f_dict["Datum der Fahrt"] = aktuelle_fahrt[start_col].strftime('%Y-%m-%d')
                    neue_zeilen.append(f_dict)
                
                final_df = pd.DataFrame(neue_zeilen)
                
                # Formatierung der Zeit-Spalten ohne Millisekunden
                for col in [start_col, ende_col, eingang_col, ueber_col]:
                    if col in final_df.columns:
                        final_df[col] = pd.to_datetime(final_df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Nur Wunsch-Spalten in das Excel-Blatt
                final_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=str(fahrer)[:30], index=False)
                
                # Orange Färbung anwenden
                ws = writer.sheets[str(fahrer)[:30]]
                for idx, row in enumerate(neue_zeilen, start=2):
                    if row.get("STATUS_INTERN") == "ORANGE":
                        for cell in ws[idx]:
                            cell.fill = orange_fill
                            
        st.success("✅ Smart-Analyse abgeschlossen.")
        st.download_button("Download Ergebnis", data=output.getvalue(), file_name="Uber_Check_Smart.xlsx")

    except Exception as e:
        st.error(f"Fehler: {e}")
