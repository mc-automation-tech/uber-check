import streamlit as st
import pandas as pd
import io
from datetime import timedelta

st.set_page_config(page_title="Uber Logik Full-Data", layout="wide")
st.title("🚗 Fahrtenbuch-Generator (Alle Spalten + Diskret)")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    speed_kmh = st.number_input("Schnitt-KM/H für Leerzeiten", value=25)
    st.info("Alle Original-Spalten bleiben erhalten. Lücken werden zwischen Zielort A und Abholort B geschlossen.")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

# Deine exakte Spaltenliste
ALLE_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", 
    "Uhrzeit der Auftragsuebermittlung", 
    "Datum der Fahrt", 
    "Fahrtstatus", 
    "Standort des Fahrzeugs bei Auftragsuebermittlung", 
    "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", 
    "Kennzeichen", 
    "Fahrzeugtyp", 
    "Fahrername", 
    "Fahrpreis", 
    "Kilometer", 
    "Abholort", 
    "Zielort"
]

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).strip() for c in df.columns]
        
        # Zeit-Korrektur für Stabilität
        df["Uhrzeit des Fahrtbeginns"] = pd.to_datetime(df["Uhrzeit des Fahrtbeginns"], errors='coerce')
        df["Uhrzeit des Fahrtendes"] = pd.to_datetime(df["Uhrzeit des Fahrtendes"], errors='coerce')
        df = df.dropna(subset=["Kennzeichen", "Uhrzeit des Fahrtbeginns"])

        if not df.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for kennzeichen, k_group in df.groupby("Kennzeichen"):
                    k_group['Tag'] = k_group['Uhrzeit des Fahrtbeginns'].dt.date
                    final_rows = []

                    for tag, tag_group in k_group.groupby('Tag'):
                        tag_group = tag_group.sort_values("Uhrzeit des Fahrtbeginns")
                        
                        for i in range(len(tag_group)):
                            fahrt = tag_group.iloc[i]
                            f_start = fahrt["Uhrzeit des Fahrtbeginns"]
                            f_ende = fahrt["Uhrzeit des Fahrtendes"] if pd.notnull(fahrt["Uhrzeit des Fahrtendes"]) else f_start + timedelta(minutes=15)
                            
                            # 1. Echte Fahrt (alle Spalten übernehmen)
                            f_dict = {c: fahrt.get(c, "") for c in ALLE_SPALTEN}
                            # Zeiten für Excel schön formatieren
                            f_dict["Uhrzeit des Fahrtbeginns"] = f_start.strftime('%Y-%m-%d %H:%M:%S')
                            f_dict["Uhrzeit des Fahrtendes"] = f_ende.strftime('%Y-%m-%d %H:%M:%S')
                            if pd.notnull(f_dict.get("Datum/Uhrzeit Auftragseingang")):
                                f_dict["Datum/Uhrzeit Auftragseingang"] = pd.to_datetime(f_dict["Datum/Uhrzeit Auftragseingang"]).strftime('%Y-%m-%d %H:%M:%S')
                            
                            final_rows.append(f_dict)

                            # 2. Lücke zum nächsten Auftrag füllen (Leerfahrt)
                            if i < len(tag_group) - 1:
                                naechste = tag_group.iloc[i+1]
                                n_start = naechste["Uhrzeit des Fahrtbeginns"]
                                luecke_min = (n_start - f_ende).total_seconds() / 60
                                
                                if luecke_min > 1:
                                    leer = {c: "" for c in ALLE_SPALTEN}
                                    leer.update({
                                        "Datum der Fahrt": tag,
                                        "Fahrtstatus": "Betriebsfahrt",
                                        "Uhrzeit des Fahrtbeginns": f_ende.strftime('%Y-%m-%d %H:%M:%S'),
                                        "Uhrzeit des Fahrtendes": n_start.strftime('%Y-%m-%d %H:%M:%S'),
                                        "Kennzeichen": kennzeichen,
                                        "Fahrzeugtyp": fahrt.get("Fahrzeugtyp", ""),
                                        "Fahrername": fahrt.get("Fahrername", ""),
                                        "Abholort": fahrt.get("Zielort", ""), # Startet am Ende der letzten Fahrt
                                        "Zielort": naechste.get("Abholort", ""), # Endet am Start der nächsten Fahrt
                                        "Kilometer": round(luecke_min * (speed_kmh / 60), 2),
                                        "Fahrpreis": 0 # Kein Preis für Leerfahrt
                                    })
                                    final_rows.append(leer)

                    res_df = pd.DataFrame(final_rows)
                    # Sicherstellen, dass die Reihenfolge der Spalten genau wie gewünscht ist
                    res_df = res_df[ALLE_SPALTEN]
                    res_df.to_excel(writer, sheet_name=str(kennzeichen)[:30], index=False)

            st.success(f"✅ Datei mit allen {len(ALLE_SPALTEN)} Spalten erstellt!")
            st.download_button("Excel mit allen Feldern herunterladen", data=output.getvalue(), file_name="Uber_Fahrtenbuch_Komplett.xlsx")
    except Exception as e:
        st.error(f"Fehler: {e}")
