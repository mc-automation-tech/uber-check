import streamlit as st
import pandas as pd
import io
import math
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-Logik Pro", layout="wide")
st.title("🚗 Uber Fahrtenbuch-Generator")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏢 Betriebssitz Daten")
    str_hnr = st.text_input("Straße & Hausnummer", "Falderstraße 3")
    plz = st.text_input("PLZ", "50999")
    ort = st.text_input("Ort", "Köln")
    bs_coords = st.text_input("GPS Betriebssitz (Lat Lon)", "50.885277 6.9877386")
    st.markdown("---")
    speed_kmh = st.number_input("Durchschnitts-KM/H", value=50)
    # Neu: Regler für die Farblogik
    limit_min = st.slider("Ab wann Orange (Rückfahrt)? (Minuten)", 5, 45, 15)
    st.info("Unter diesem Wert = Grün (Wenden), darüber = Orange (Rückfahrt Basis).")

full_bs_address = f"{str_hnr}, {plz} {ort}"

def calculate_current_gps(start_gps_str, target_gps_str, minutes, speed):
    try:
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
    except: return start_gps_str

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

        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.contains("abgeschlossen", case=False, na=False)]
        
        df = df.dropna(subset=["Fahrername", "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes"])

        if not df.empty:
            time_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
                         "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
            for col in time_cols:
                df[col] = pd.to_datetime(df[col], errors='coerce')

            output = io.BytesIO()
            orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
            green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for fahrer, group in df.groupby("Fahrername"):
                    f_df = group.sort_values("Uhrzeit des Fahrtbeginns").copy()
                    neue_zeilen = []
                    
                    for i in range(len(f_df)):
                        aktuelle_fahrt = f_df.iloc[i]
                        if i > 0:
                            vorherige_fahrt = f_df.iloc[i-1]
                            pause_min = (aktuelle_fahrt["Datum/Uhrzeit Auftragseingang"] - vorherige_fahrt["Uhrzeit des Fahrtendes"]).total_seconds() / 60
                            
                            if pause_min > 5:
                                leer = {c: "" for c in WUNSCH_SPALTEN}
                                leer["Fahrername"] = fahrer
                                leer["Datum der Fahrt"] = aktuelle_fahrt["Uhrzeit des Fahrtbeginns"].strftime('%Y-%m-%d')
                                leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt["Uhrzeit des Fahrtendes"].strftime('%Y-%m-%d %H:%M:%S')
                                leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt["Datum/Uhrzeit Auftragseingang"].strftime('%Y-%m-%d %H:%M:%S')
                                leer["Abholort"] = vorherige_fahrt["Zielort"]
                                leer["Kilometer"] = round(pause_min * (speed_kmh / 60), 2)
                                last_gps = str(vorherige_fahrt["Standort des Fahrzeugs bei Auftragsuebermittlung"])
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = calculate_current_gps(last_gps, bs_coords, pause_min, speed_kmh)
                                
                                if pause_min <= limit_min:
                                    leer["Zielort"] = aktuelle_fahrt["Abholort"]
                                    leer["_COLOR"] = "GREEN"
                                else:
                                    leer["Zielort"] = f"Betriebssitz ({full_bs_address})"
                                    leer["_COLOR"] = "ORANGE"
                                neue_zeilen.append(leer)
                        
                        f_dict = aktuelle_fahrt.to_dict()
                        f_dict["Datum der Fahrt"] = aktuelle_fahrt["Uhrzeit des Fahrtbeginns"].strftime('%Y-%m-%d')
                        for k in time_cols:
                            if k in f_dict and pd.notnull(f_dict[k]):
                                f_dict[k] = pd.to_datetime(f_dict[k]).strftime('%Y-%m-%d %H:%M:%S')
                        f_dict["_COLOR"] = "WHITE"
                        neue_zeilen.append(f_dict)
                    
                    # Erstellen des Sheets
                    final_df = pd.DataFrame(neue_zeilen)
                    sheet_name = "".join([c for c in str(fahrer) if c.isalnum() or c==' '])[:30].strip()
                    final_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # --- AUTOMATISCHE SPALTENBREITE & FARBEN ---
                    ws = writer.sheets[sheet_name]
                    for col_idx, column in enumerate(ws.columns, 1):
                        max_length = 0
                        column_letter = ws.cell(row=1, column=col_idx).column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except: pass
                        ws.column_dimensions[column_letter].width = max_length + 4 # Puffer
                    
                    for idx, row in enumerate(neue_zeilen, start=2):
                        c = row.get("_COLOR")
                        if c == "ORANGE":
                            for cell in ws[idx]: cell.fill = orange_fill
                        elif c == "GREEN":
                            for cell in ws[idx]: cell.fill = green_fill
            
            st.success("✅ Analyse fertig. Spalten wurden automatisch angepasst.")
            st.download_button("Excel-Datei herunterladen", data=output.getvalue(), file_name="Uber_Fahrtenbuch_Optimiert.xlsx")
    except Exception as e:
        st.error(f"Fehler: {e}")
