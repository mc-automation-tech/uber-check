import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-GPS Pro", layout="wide")
st.title("🚗 Uber Fahrtenbuch: GPS & Rückfahrt-Automatik")

# --- SIDEBAR: KONFIGURATION ---
with st.sidebar:
    st.header("🏢 Betriebssitz Daten")
    str_hnr = st.text_input("Straße & Hausnummer", "Falderstraße 3")
    plz = st.text_input("PLZ", "50999")
    ort = st.text_input("Ort", "Köln")
    bs_coords = st.text_input("GPS-Koordinaten Betriebssitz (Lat Lon)", "50.8800 6.9900")
    
    st.markdown("---")
    kmh = st.number_input("Durchschnitts-KM/H für Leerfahrt", value=50)
    st.info("Das Programm berechnet die GPS-Position des Fahrzeugs auf dem Rückweg zum Betriebssitz.")

full_bs_address = f"{str_hnr}, {plz} {ort}"

# --- DATEI HOCHLADEN ---
uploaded_file = st.file_uploader("Uber Liste (CSV oder Excel) hochladen", type=["xlsx", "csv"])

WUNSCH_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt",
    "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns",
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername",
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

def interpolate_gps(start_gps_str, home_gps_str, minutes, speed):
    """Berechnet die Position auf dem Weg nach Hause nach X Minuten."""
    try:
        lat1, lon1 = map(float, start_gps_str.split())
        lat2, lon2 = map(float, home_gps_str.split())
        
        # Zurückgelegte Distanz in Grad (vereinfacht für Kurzstrecken)
        # 50 km/h sind ca. 0.83 km/min. 1 Grad Breitengrad sind ca. 111 km.
        dist_km = minutes * (speed / 60)
        total_dist_geo = ((lat2-lat1)**2 + (lon2-lon1)**2)**0.5
        total_dist_km = total_dist_geo * 111
        
        if total_dist_km <= dist_km or total_dist_km == 0:
            return home_gps_str # Er ist schon angekommen
        
        ratio = dist_km / total_dist_km
        new_lat = lat1 + (lat2 - lat1) * ratio
        new_lon = lon1 + (lon2 - lon1) * ratio
        
        return f"{round(new_lat, 6)} {round(new_lon, 6)}"
    except:
        return start_gps_str

if uploaded_file:
    try:
        # Einlesen
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]

        # Zeitformate
        start_col, ende_col, eingang_col = "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang"
        gps_col = "Standort des Fahrzeugs bei Auftragsuebermittlung"
        
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
                            leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt[ende_col].strftime('%Y-%m-%d %H:%M:%S')
                            leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt[eingang_col].strftime('%Y-%m-%d %H:%M:%S')
                            leer["Abholort"] = vorherige_fahrt["Zielort"]
                            
                            # KM-Berechnung
                            leer["Kilometer"] = round(pause_min * (kmh/60), 2)
                            
                            # GPS-Berechnung (Wo war er beim neuen Auftragseingang?)
                            last_gps = str(vorherige_fahrt[gps_col])
                            leer[gps_col] = interpolate_gps(last_gps, bs_coords, pause_min, kmh)
                            
                            if pause_min <= 15:
                                leer["Zielort"] = aktuelle_fahrt["Abholort"]
                                leer["_COLOR"] = "GREEN"
                            else:
                                leer["Zielort"] = f"Betriebssitz ({full_bs_address})"
                                leer["_COLOR"] = "ORANGE"
                            neue_zeilen.append(leer)
                    
                    f_dict = aktuelle_fahrt.to_dict()
                    f_dict["Datum der Fahrt"] = aktuelle_fahrt[start_col].strftime('%Y-%m-%d')
                    for k in [start_col, ende_col, eingang_col, "Uhrzeit der Auftragsuebermittlung"]:
                        if k in f_dict and pd.notnull(f_dict[k]):
                            f_dict[k] = pd.to_datetime(f_dict[k]).strftime('%Y-%m-%d %H:%M:%S')
                    f_dict["_COLOR"] = "WHITE"
                    neue_zeilen.append(f_dict)
                
                final_df = pd.DataFrame(neue_zeilen)
                final_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=str(fahrer)[:30], index=False)
                
                ws = writer.sheets[str(fahrer)[:30]]
                for idx, row in enumerate(neue_zeilen, start=2):
                    c = row.get("_COLOR")
                    if c == "ORANGE":
                        for cell in ws[idx]: cell.fill = orange_fill
                    elif c == "GREEN":
                        for cell in ws[idx]: cell.fill = green_fill
                            
        st.success("✅ Fertig! GPS-Positionen wurden für die Leerfahrten berechnet.")
        st.download_button("Download Experten-Fahrtenbuch", data=output.getvalue(), file_name="Uber_Check_GPS_Pro.xlsx")

    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
