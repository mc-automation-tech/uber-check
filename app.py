import streamlit as st
import pandas as pd
import io
import math
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-Logik Pro", layout="wide")
st.title("🚗 Uber Fahrtenbuch & Rückfahrt-Simulation")

# --- SIDEBAR KONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Betriebssitz-Daten")
    bs_adresse = st.text_input("Adresse (für Zielort-Spalte)", "Falderstraße 3, 50999 Köln")
    bs_coords = st.text_input("GPS-Koordinaten (für Standort-Spalte)", "50.8800 6.9900")
    st.info("Das Programm berechnet die Rückfahrtzeit mit ca. 30 km/h (Stadtverkehr).")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

WUNSCH_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt",
    "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns",
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername",
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

def calculate_return_time(pause_min):
    # Annahme: Durchschnittlich 15-20 Min Rückfahrt in der Stadt
    # Hier könnte man später eine echte Distanz-Logik einbauen
    return min(pause_min, 20) 

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]

        # Zeitspalten
        start_col, ende_col, eingang_col = "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang"
        for col in [start_col, ende_col, eingang_col]:
            df[col] = pd.to_datetime(df[col], errors='coerce')

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for fahrer in df["Fahrername"].unique():
                f_df = df[df["Fahrername"] == fahrer].sort_values(start_col).copy()
                neue_zeilen = []
                
                for i in range(len(f_df)):
                    aktuelle_fahrt = f_df.iloc[i]
                    if i > 0:
                        vorherige_fahrt = f_df.iloc[i-1]
                        pause_min = (aktuelle_fahrt[eingang_col] - vorherige_fahrt[ende_col]).total_seconds() / 60
                        
                        if pause_min > 5:
                            leer = {c: "" for c in WUNSCH_SPALTEN}
                            leer["Fahrername"] = fahrer
                            leer["Datum der Fahrt"] = aktuelle_fahrt[start_col].strftime('%Y-%m-%d')
                            
                            # Logik für die Rückfahrtzeit
                            rueckfahrt_dauer = 15 # Wir nehmen 15 Min als Standard-Rückreisezeit an
                            
                            if pause_min <= 15:
                                # GRÜN: Er war noch auf dem Weg oder kurz davor
                                leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt[ende_col].strftime('%Y-%m-%d %H:%M:%S')
                                leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt[eingang_col].strftime('%Y-%m-%d %H:%M:%S')
                                leer["Abholort"] = vorherige_fahrt["Zielort"]
                                leer["Zielort"] = aktuelle_fahrt["Abholort"]
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = "GPS: In Bewegung"
                                leer["_COLOR"] = "GREEN"
                            else:
                                # ORANGE: Rückfahrtpflicht zum Betriebssitz
                                leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt[ende_col].strftime('%Y-%m-%d %H:%M:%S')
                                # Er berechnet, dass er nach 15 Min am Betriebssitz ankommt
                                ankunft_bs = vorherige_fahrt[ende_col] + pd.Timedelta(minutes=rueckfahrt_dauer)
                                leer["Uhrzeit des Fahrtendes"] = ankunft_bs.strftime('%Y-%m-%d %H:%M:%S')
                                
                                leer["Abholort"] = vorherige_fahrt["Zielort"]
                                leer["Zielort"] = f"Betriebssitz ({bs_adresse})"
                                # Hier setzen wir jetzt echte Koordinaten ein!
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = bs_coords
                                leer["_COLOR"] = "ORANGE"
                            neue_zeilen.append(leer)
                    
                    # Originale Fahrt
                    f_dict = aktuelle_fahrt.to_dict()
                    f_dict["Datum der Fahrt"] = aktuelle_fahrt[start_col].strftime('%Y-%m-%d')
                    # Zeiten hübsch machen
                    for k in [start_col, ende_col, eingang_col, "Uhrzeit der Auftragsuebermittlung"]:
                        if k in f_dict and pd.notnull(f_dict[k]):
                            f_dict[k] = pd.to_datetime(f_dict[k]).strftime('%Y-%m-%d %H:%M:%S')
                    f_dict["_COLOR"] = "WHITE"
                    neue_zeilen.append(f_dict)
                
                final_df = pd.DataFrame(neue_zeilen)
                final_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=str(fahrer)[:30], index=False)
                
                ws = writer.sheets[str(fahrer)[:30]]
                for idx, row in enumerate(neue_zeilen, start=2):
                    color = row.get("_COLOR")
                    if color == "ORANGE":
                        for cell in ws[idx]: cell.fill = orange_fill
                    elif color == "GREEN":
                        for cell in ws[idx]: cell.fill = green_fill
                            
        st.success("✅ Analyse abgeschlossen. Koordinaten und Zeiten wurden simuliert.")
        st.download_button("Download korrigiertes Fahrtenbuch", data=output.getvalue(), file_name="Uber_Fahrtenbuch_Pro.xlsx")

    except Exception as e:
        st.error(f"Fehler: {e}")
