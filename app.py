import streamlit as st
import pandas as pd
import io
import math
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-Logik Pro Plus", layout="wide")
st.title("🚗 Uber Fahrtenbuch - Lückenlos & Aktiv")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏢 Betriebssitz Daten")
    str_hnr = st.text_input("Straße & Hausnummer", "Alfred-Nobel-Straße 29")
    plz = st.text_input("PLZ", "50226")
    ort = st.text_input("Ort", "Frechen")
    bs_coords = st.text_input("GPS Betriebssitz (Lat Lon)", "50.914312 6.819731")
    st.markdown("---")
    speed_kmh = st.number_input("Durchschnitts-KM/H für Leerfahrten", value=40)
    st.warning("HINWEIS: Dieses Programm erzeugt Zusatzzeilen, um jede Minute der Schicht zu belegen.")

full_bs_address = f"{str_hnr}, {plz} {ort}"

# --- HILFSFUNKTION FÜR GPS ---
def calculate_current_gps(start_gps_str, target_gps_str, minutes, speed):
    try:
        if not start_gps_str or start_gps_str == "\\N": return target_gps_str
        s_lat, s_lon = map(float, str(start_gps_str).split())
        t_lat, t_lon = map(float, str(target_gps_str).split())
        dist_traveled = minutes * (speed / 60)
        deg_dist = math.sqrt((t_lat - s_lat)**2 + (t_lon - s_lon)**2)
        km_dist = deg_dist * 111 
        if km_dist == 0 or dist_traveled >= km_dist: return target_gps_str
        ratio = dist_traveled / km_dist
        new_lat = s_lat + (t_lat - s_lat) * ratio
        new_lon = s_lon + (t_lon - s_lon) * ratio
        return f"{round(new_lat, 6)} {round(new_lon, 6)}"
    except: return bs_coords

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

WUNSCH_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt",
    "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns",
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrername",
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]
        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.contains("abgeschlossen", case=False, na=False)]
        df = df.dropna(subset=["Kennzeichen", "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes"])

        if not df.empty:
            time_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang"]
            for col in time_cols:
                df[col] = pd.to_datetime(df[col], errors='coerce')

            output = io.BytesIO()
            fill_orange = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for kennzeichen, group in df.groupby("Kennzeichen"):
                    f_df = group.sort_values("Uhrzeit des Fahrtbeginns").copy()
                    neue_zeilen = []
                    
                    for i in range(len(f_df)):
                        aktuelle_fahrt = f_df.iloc[i]
                        
                        if i > 0:
                            vorherige_fahrt = f_df.iloc[i-1]
                            # LÜCKE FÜLLEN
                            diff_min = (aktuelle_fahrt["Uhrzeit des Fahrtbeginns"] - vorherige_fahrt["Uhrzeit des Fahrtendes"]).total_seconds() / 60
                            
                            if diff_min > 2: # Nur wenn Lücke größer als 2 Min
                                leer = {c: "" for c in WUNSCH_SPALTEN}
                                leer["Kennzeichen"] = kennzeichen
                                leer["Fahrername"] = aktuelle_fahrt["Fahrername"]
                                leer["Datum der Fahrt"] = aktuelle_fahrt["Uhrzeit des Fahrtbeginns"].strftime('%Y-%m-%d')
                                leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt["Uhrzeit des Fahrtendes"].strftime('%Y-%m-%d %H:%M:%S')
                                leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt["Uhrzeit des Fahrtbeginns"].strftime('%Y-%m-%d %H:%M:%S')
                                leer["Abholort"] = vorherige_fahrt["Zielort"]
                                leer["Zielort"] = aktuelle_fahrt["Abholort"]
                                leer["Kilometer"] = round(diff_min * (speed_kmh / 60), 2)
                                leer["_COLOR"] = "ORANGE"
                                # GPS Simulation: Wo war er beim neuen Ruf?
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = calculate_current_gps(
                                    str(vorherige_fahrt.get("Standort des Fahrzeugs bei Auftragsuebermittlung", bs_coords)), 
                                    bs_coords, diff_min/2, speed_kmh)
                                neue_zeilen.append(leer)
                        
                        # ECHTE FAHRT
                        f_dict = aktuelle_fahrt.to_dict()
                        for k in time_cols:
                            if k in f_dict and pd.notnull(f_dict[k]):
                                f_dict[k] = f_dict[k].strftime('%Y-%m-%d %H:%M:%S')
                        f_dict["_COLOR"] = "WHITE"
                        neue_zeilen.append(f_dict)
                    
                    # Sheet erstellen
                    res_df = pd.DataFrame(neue_zeilen)
                    sheet_name = "".join([c for c in str(kennzeichen) if c.isalnum() or c==' '])[:30].strip()
                    res_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    ws = writer.sheets[sheet_name]
                    for idx, row in enumerate(neue_zeilen, start=2):
                        if row.get("_COLOR") == "ORANGE":
                            for cell in ws[idx]: cell.fill = fill_orange

            st.success("✅ Auswertung fertig. Alle Lücken wurden durch 'Anschlussfahrten' geschlossen.")
            st.download_button("Datei herunterladen", data=output.getvalue(), file_name="Uber_Lueckenlos_Pro.xlsx")
    except Exception as e:
        st.error(f"Fehler: {e}")
