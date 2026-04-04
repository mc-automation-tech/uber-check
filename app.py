import streamlit as st
import pandas as pd
import io
from datetime import timedelta
import math

st.set_page_config(page_title="Uber Smart-Logik Ultimate", layout="wide")
st.title("🚗 Fahrtenbuch-Generator (Gesetzes-Modus)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏢 Betriebssitz Daten")
    str_hnr = st.text_input("Straße & Hausnummer", "Alfred-Nobel-Straße 29")
    plz = st.text_input("PLZ", "50226")
    ort = st.text_input("Ort", "Frechen")
    st.markdown("---")
    speed_kmh = st.number_input("Schnitt-KM/H (Leerfahrten)", value=35)
    st.info("Regel: 1. Fahrt startet immer in Frechen. Nach 6 Std. erfolgt 30 Min. Pause.")

full_bs_address = f"{str_hnr}, {plz} {ort}"

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

# Diese Spalten müssen in der finalen Excel sein
WUNSCH_SPALTEN = [
    "Datum der Fahrt", "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
    "Kennzeichen", "Fahrername", "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Datei laden
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Spaltennamen säubern
        df.columns = [str(c).strip() for c in df.columns]
        
        # WICHTIG: Zeit-Korrektur für "\N" Fehler
        time_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes"]
        for col in time_cols:
            if col in df.columns:
                # errors='coerce' verwandelt \N in ein ungültiges Datum (NaT), was wir dann löschen
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Zeilen ohne Zeit oder Kennzeichen löschen
        df = df.dropna(subset=["Kennzeichen", "Uhrzeit des Fahrtbeginns"])
        
        if df.empty:
            st.error("Keine gültigen Daten gefunden. Prüfe die Spaltenköpfe.")
        else:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for kennzeichen, k_group in df.groupby("Kennzeichen"):
                    k_group['Tag'] = k_group['Uhrzeit des Fahrtbeginns'].dt.date
                    final_rows = []

                    for tag, tag_group in k_group.groupby('Tag'):
                        tag_group = tag_group.sort_values("Uhrzeit des Fahrtbeginns")
                        
                        # --- 1. START VOM BETRIEBSSITZ ---
                        schicht_start_zeit = tag_group.iloc[0]["Uhrzeit des Fahrtbeginns"]
                        anfahrt_start = schicht_start_zeit - timedelta(minutes=15)
                        
                        start_row = {c: "" for c in WUNSCH_SPALTEN}
                        start_row.update({
                            "Datum der Fahrt": tag,
                            "Uhrzeit des Fahrtbeginns": anfahrt_start.strftime('%H:%M:%S'),
                            "Uhrzeit des Fahrtendes": schicht_start_zeit.strftime('%H:%M:%S'),
                            "Kennzeichen": kennzeichen,
                            "Fahrername": tag_group.iloc[0].get("Fahrername", ""),
                            "Abholort": f"Betriebssitz ({full_bs_address})",
                            "Zielort": tag_group.iloc[0].get("Abholort", "Start"),
                            "Kilometer": 8.5,
                            "_TYPE": "START"
                        })
                        final_rows.append(start_row)

                        # --- 2. FAHRTEN & LÜCKEN & PAUSEN ---
                        kumulierte_arbeitszeit_min = 0

                        for i in range(len(tag_group)):
                            fahrt = tag_group.iloc[i]
                            
                            f_start = fahrt["Uhrzeit des Fahrtbeginns"]
                            f_ende = fahrt["Uhrzeit des Fahrtendes"]
                            
                            # Wenn Ende fehlt, schätze 15 Min
                            if pd.isnull(f_ende):
                                f_ende = f_start + timedelta(minutes=15)
                            
                            # Arbeitszeit tracken
                            f_dauer = (f_ende - f_start).total_seconds() / 60
                            kumulierte_arbeitszeit_min += f_dauer

                            # Pause nach 6 Stunden (360 Min)
                            if kumulierte_arbeitszeit_min > 360:
                                pause_row = {c: "" for c in WUNSCH_SPALTEN}
                                pause_row.update({
                                    "Datum der Fahrt": tag,
                                    "Uhrzeit des Fahrtbeginns": f_start.strftime('%H:%M:%S'),
                                    "Uhrzeit des Fahrtendes": (f_start + timedelta(minutes=30)).strftime('%H:%M:%S'),
                                    "Kennzeichen": kennzeichen,
                                    "Fahrername": fahrt.get("Fahrername", ""),
                                    "Abholort": "PAUSE", "Zielort": "PAUSE", "Kilometer": 0
                                })
                                final_rows.append(pause_row)
                                kumulierte_arbeitszeit_min = 0 # Reset
                                # Echte Fahrt um 30 Min verschieben, damit sie nach der Pause liegt
                                f_start += timedelta(minutes=30)
                                f_ende += timedelta(minutes=30)

                            # Echte Fahrt hinzufügen
                            f_dict = {c: fahrt.get(c, "") for c in WUNSCH_SPALTEN}
                            f_dict.update({
                                "Datum der Fahrt": tag,
                                "Uhrzeit des Fahrtbeginns": f_start.strftime('%H:%M:%S'),
                                "Uhrzeit des Fahrtendes": f_ende.strftime('%H:%M:%S'),
                                "Kennzeichen": kennzeichen
                            })
                            final_rows.append(f_dict)
                            
                            # Lücke füllen
                            if i < len(tag_group) - 1:
                                n_fahrt = tag_group.iloc[i+1]
                                n_start = n_fahrt["Uhrzeit des Fahrtbeginns"]
                                
                                luecke_min = (n_start - f_ende).total_seconds() / 60
                                if luecke_min > 1:
                                    leer = {c: "" for c in WUNSCH_SPALTEN}
                                    leer.update({
                                        "Datum der Fahrt": tag,
                                        "Uhrzeit des Fahrtbeginns": f_ende.strftime('%H:%M:%S'),
                                        "Uhrzeit des Fahrtendes": n_start.strftime('%H:%M:%S'),
                                        "Kennzeichen": kennzeichen,
                                        "Fahrername": fahrt.get("Fahrername", ""),
                                        "Abholort": fahrt.get("Zielort", ""),
                                        "Zielort": n_fahrt.get("Abholort", ""),
                                        "Kilometer": round(luecke_min * (speed_kmh / 60), 2)
                                    })
                                    final_rows.append(leer)

                    # In Excel schreiben
                    res_df = pd.DataFrame(final_rows)
                    sheet_name = str(kennzeichen).replace("/", "-")[:30]
                    res_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=sheet_name, index=False)

            st.success("✅ Fehler behoben! Datei ist bereit.")
            st.download_button("Excel herunterladen", data=output.getvalue(), file_name="Uber_Fahrtenbuch_Fix.xlsx")
            
    except Exception as e:
        st.error(f"Kritischer Fehler: {e}")
