import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-Logik Pro", layout="wide")
st.title("🚗 Uber Fahrtenbuch-Generator")

# --- SIDEBAR KONFIGURATION ---
with st.sidebar:
    st.header("🏢 Betriebssitz Details")
    str_hnr = st.text_input("Straße & Hausnummer", "Falderstraße 3")
    plz = st.text_input("PLZ", "50999")
    ort = st.text_input("Ort", "Köln")
    
    st.markdown("---")
    st.subheader("🌐 Standort-Optionen")
    bs_coords = st.text_input("GPS-Koordinaten (Optional)", "50.8800 6.9900")
    rueckfahrt_dauer = st.slider("Minuten für Rückfahrt", 5, 45, 15)

# Adresse zusammenbauen
bs_adresse_full = f"{str_hnr}, {plz} {ort}"

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
                            leer["Uhrzeit des Fahrtbeginns"] = vorherige_fahrt[ende_col].strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Bei Pausen > Schwellenwert: Rückfahrt zum Betriebssitz (Orange)
                            if pause_min > rueckfahrt_dauer:
                                ankunft_bs = vorherige_fahrt[ende_col] + pd.Timedelta(minutes=rueckfahrt_dauer)
                                leer["Uhrzeit des Fahrtendes"] = ankunft_bs.strftime('%Y-%m-%d %H:%M:%S')
                                leer["Abholort"] = vorherige_fahrt["Zielort"]
                                leer["Zielort"] = f"Betriebssitz ({bs_adresse_full})"
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = bs_coords if bs_coords else "Betriebssitz"
                                leer["_COLOR"] = "ORANGE"
                            else:
                                # Kurze Pause: Wendemanöver / Bereitstellung (Grün)
                                leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt[eingang_col].strftime('%Y-%m-%d %H:%M:%S')
                                leer["Abholort"] = vorherige_fahrt["Zielort"]
                                leer["Zielort"] = aktuelle_fahrt["Abholort"]
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = "GPS: Wendepunkt/Anfahrt"
                                leer["_COLOR"] = "GREEN"
                            neue_zeilen.append(leer)
                    
                    # Originale Fahrt
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
                            
        st.success("✅ Dokument wurde mit der neuen Adress-Logik erstellt.")
        st.download_button("Download Fahrtenbuch", data=output.getvalue(), file_name="Uber_Fahrtenbuch_Expert.xlsx")

    except Exception as e:
        st.error(f"Fehler: {e}")
