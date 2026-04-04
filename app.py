import streamlit as st
import pandas as pd
import io
from datetime import timedelta

st.set_page_config(page_title="Uber Fahrtenbuch Profi", layout="wide")
st.title("🚗 Fahrtenbuch-Generator (Real-Adressen Modus)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏢 Betriebssitz Konfiguration")
    bs_adresse = st.text_input("Vollständige Adresse Betriebssitz", "Alfred-Nobel-Straße 29, 50226 Frechen")
    st.markdown("---")
    speed_kmh = st.number_input("Schnitt-KM/H für Anfahrten", value=30)
    st.info("Jede Schicht beginnt an der Alfred-Nobel-Str. und kehrt bei Pausen dorthin zurück.")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

WUNSCH_SPALTEN = [
    "Datum der Fahrt", "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
    "Kennzeichen", "Fahrername", "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Datei einlesen
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = [str(c).strip() for c in df.columns]
        
        # Zeit-Korrektur (wichtig wegen \N Fehlern)
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
                        
                        # --- 1. SCHICHT-START (Anfahrt zum 1. Kunden) ---
                        erstfahrt = tag_group.iloc[0]
                        anfahrt_dauer = 15 # wir nehmen 15 Min Anfahrt an
                        start_zeit = erstfahrt["Uhrzeit des Fahrtbeginns"] - timedelta(minutes=anfahrt_dauer)
                        
                        start_row = {c: "" for c in WUNSCH_SPALTEN}
                        start_row.update({
                            "Datum der Fahrt": tag,
                            "Uhrzeit des Fahrtbeginns": start_zeit.strftime('%H:%M:%S'),
                            "Uhrzeit des Fahrtendes": erstfahrt["Uhrzeit des Fahrtbeginns"].strftime('%H:%M:%S'),
                            "Kennzeichen": kennzeichen,
                            "Fahrername": erstfahrt.get("Fahrername", ""),
                            "Abholort": bs_adresse, # START ADRESSE FRECHEN
                            "Zielort": erstfahrt.get("Abholort", "Kunde"),
                            "Kilometer": 7.2
                        })
                        final_rows.append(start_row)

                        # --- 2. FAHRTEN UND RÜCKKEHR ---
                        arbeitszeit_min = 0

                        for i in range(len(tag_group)):
                            fahrt = tag_group.iloc[i]
                            f_start = fahrt["Uhrzeit des Fahrtbeginns"]
                            f_ende = fahrt["Uhrzeit des Fahrtendes"] if pd.notnull(fahrt["Uhrzeit des Fahrtendes"]) else f_start + timedelta(minutes=15)
                            
                            # Pause nach 6 Std einfügen
                            dauer = (f_ende - f_start).total_seconds() / 60
                            arbeitszeit_min += dauer
                            if arbeitszeit_min > 360:
                                p_row = {c: "" for c in WUNSCH_SPALTEN}
                                p_row.update({
                                    "Datum der Fahrt": tag,
                                    "Uhrzeit des Fahrtbeginns": f_start.strftime('%H:%M:%S'),
                                    "Uhrzeit des Fahrtendes": (f_start + timedelta(minutes=30)).strftime('%H:%M:%S'),
                                    "Kennzeichen": kennzeichen, "Fahrername": fahrt.get("Fahrername", ""),
                                    "Abholort": "PAUSE (Alfred-Nobel-Str)", "Zielort": "PAUSE (Alfred-Nobel-Str)", "Kilometer": 0
                                })
                                final_rows.append(p_row)
                                arbeitszeit_min = 0
                                f_start += timedelta(minutes=30)
                                f_ende += timedelta(minutes=30)

                            # Echte Fahrt
                            f_dict = {c: fahrt.get(c, "") for c in WUNSCH_SPALTEN}
                            f_dict.update({
                                "Datum der Fahrt": tag,
                                "Uhrzeit des Fahrtbeginns": f_start.strftime('%H:%M:%S'),
                                "Uhrzeit des Fahrtendes": f_ende.strftime('%H:%M:%S')
                            })
                            final_rows.append(f_dict)

                            # Lücke füllen: Rückfahrt zum Betriebssitz + Anfahrt zum nächsten
                            if i < len(tag_group) - 1:
                                naechste = tag_group.iloc[i+1]
                                luecke_min = (naechste["Uhrzeit des Fahrtbeginns"] - f_ende).total_seconds() / 60
                                
                                if luecke_min > 2:
                                    # Rückfahrt zum Betriebssitz
                                    mitte_zeit = f_ende + timedelta(minutes=luecke_min/2)
                                    rueck = {c: "" for c in WUNSCH_SPALTEN}
                                    rueck.update({
                                        "Datum der Fahrt": tag,
                                        "Uhrzeit des Fahrtbeginns": f_ende.strftime('%H:%M:%S'),
                                        "Uhrzeit des Fahrtendes": mitte_zeit.strftime('%H:%M:%S'),
                                        "Kennzeichen": kennzeichen, "Fahrername": fahrt.get("Fahrername", ""),
                                        "Abholort": fahrt.get("Zielort", ""),
                                        "Zielort": bs_adresse, # ZIEL FRECHEN
                                        "Kilometer": round((luecke_min/2) * (speed_kmh/60), 2)
                                    })
                                    final_rows.append(rueck)
                                    
                                    # Wieder Anfahrt zum nächsten Kunden
                                    anfahrt = {c: "" for c in WUNSCH_SPALTEN}
                                    anfahrt.update({
                                        "Datum der Fahrt": tag,
                                        "Uhrzeit des Fahrtbeginns": mitte_zeit.strftime('%H:%M:%S'),
                                        "Uhrzeit des Fahrtendes": naechste["Uhrzeit des Fahrtbeginns"].strftime('%H:%M:%S'),
                                        "Kennzeichen": kennzeichen, "Fahrername": fahrt.get("Fahrername", ""),
                                        "Abholort": bs_adresse, # START FRECHEN
                                        "Zielort": naechste.get("Abholort", ""),
                                        "Kilometer": round((luecke_min/2) * (speed_kmh/60), 2)
                                    })
                                    final_rows.append(anfahrt)

                    res_df = pd.DataFrame(final_rows)
                    res_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=str(kennzeichen)[:30], index=False)

            st.success("✅ Fertig! Adressen sind jetzt korrekt eingetragen.")
            st.download_button("Excel herunterladen", data=output.getvalue(), file_name="Fahrtenbuch_Frechen_Korrekt.xlsx")

    except Exception as e:
        st.error(f"Fehler: {e}")
