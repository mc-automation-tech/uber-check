import streamlit as st
import pandas as pd
import io
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Smart-Logik", layout="wide")
st.title("🚗 Uber Fahrtenbuch-Optimierer")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Konfiguration")
    betriebssitz = st.text_input("Adresse Betriebssitz", "Musterstraße 1, 12345 Stadt")
    st.info("🟢 GRÜN: Lücke < 15 Min (Anschluss)\n🟠 ORANGE: Lücke > 15 Min (Rückfahrt)")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

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
        
        # Zeit-Spalten vorbereiten
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
                            leer["Uhrzeit des Fahrtendes"] = aktuelle_fahrt[eingang_col].strftime('%Y-%m-%d %H:%M:%S')
                            leer["Abholort"] = vorherige_fahrt["Zielort"]
                            
                            if pause_min <= 15:
                                # GRÜN: Kleiner Lückenschluss
                                leer["Zielort"] = aktuelle_fahrt["Abholort"]
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = "Bereitstellung"
                                leer["_COLOR"] = "GREEN"
                            else:
                                # ORANGE: Große Rückfahrt
                                leer["Zielort"] = f"Betriebssitz ({betriebssitz})"
                                leer["Standort des Fahrzeugs bei Auftragsuebermittlung"] = betriebssitz
                                leer["_COLOR"] = "ORANGE"
                            neue_zeilen.append(leer)
                    
                    # Original-Fahrt hinzufügen
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
                    if row.get("_COLOR") == "ORANGE":
                        for cell in ws[idx]: cell.fill = orange_fill
                    elif row.get("_COLOR") == "GREEN":
                        for cell in ws[idx]: cell.fill = green_fill
                            
        st.success("✅ Fertig! Lücken sind farblich korrigiert.")
        st.download_button("Download Ergebnis-Datei", data=output.getvalue(), file_name="Uber_Check_Optimiert.xlsx")

    except Exception as e:
        st.error(f"Fehler: {e}")
