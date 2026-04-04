import streamlit as st
import pandas as pd
import io
from datetime import timedelta
from openpyxl.styles import PatternFill

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

WUNSCH_SPALTEN = [
    "Datum der Fahrt", "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
    "Kennzeichen", "Fahrername", "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(subset=["Kennzeichen", "Uhrzeit des Fahrtbeginns"])
        
        # Zeitformate korrigieren
        df["Uhrzeit des Fahrtbeginns"] = pd.to_datetime(df["Uhrzeit des Fahrtbeginns"])
        df["Uhrzeit des Fahrtendes"] = pd.to_datetime(df["Uhrzeit des Fahrtendes"])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for kennzeichen, k_group in df.groupby("Kennzeichen"):
                # Wir gehen Tag für Tag durch
                k_group['Tag'] = k_group['Uhrzeit des Fahrtbeginns'].dt.date
                final_rows = []

                for tag, tag_group in k_group.groupby('Tag'):
                    tag_group = tag_group.sort_values("Uhrzeit des Fahrtbeginns")
                    schicht_start_zeit = tag_group.iloc[0]["Uhrzeit des Fahrtbeginns"]
                    
                    # --- 1. START VOM BETRIEBSSITZ ---
                    # Wir simulieren eine 15-minütige Anfahrt von Frechen zum ersten Kunden
                    anfahrt_start = schicht_start_zeit - timedelta(minutes=15)
                    start_row = {c: "" for c in WUNSCH_SPALTEN}
                    start_row.update({
                        "Datum der Fahrt": tag,
                        "Uhrzeit des Fahrtbeginns": anfahrt_start.strftime('%H:%M:%S'),
                        "Uhrzeit des Fahrtendes": schicht_start_zeit.strftime('%H:%M:%S'),
                        "Kennzeichen": kennzeichen,
                        "Fahrername": tag_group.iloc[0]["Fahrername"],
                        "Abholort": f"Betriebssitz ({full_bs_address})",
                        "Zielort": tag_group.iloc[0]["Abholort"],
                        "Kilometer": 8.5, # Pauschale Anfahrt aus Frechen
                        "_TYPE": "START"
                    })
                    final_rows.append(start_row)

                    # --- 2. FAHRTEN & LÜCKEN & PAUSEN ---
                    letzte_zeit = schicht_start_zeit
                    schicht_dauer_min = 0

                    for i in range(len(tag_group)):
                        fahrt = tag_group.iloc[i]
                        
                        # Arbeitszeit tracken für Pause
                        dauer = (fahrt["Uhrzeit des Fahrtendes"] - fahrt["Uhrzeit des Fahrtbeginns"]).total_seconds() / 60
                        schicht_dauer_min += dauer

                        # Check: Nach 6 Stunden (360 Min) eine Pause einlegen
                        if schicht_dauer_min > 360:
                            pause_row = {c: "" for c in WUNSCH_SPALTEN}
                            p_start = fahrt["Uhrzeit des Fahrtbeginns"] - timedelta(minutes=30)
                            pause_row.update({
                                "Datum der Fahrt": tag,
                                "Uhrzeit des Fahrtbeginns": p_start.strftime('%H:%M:%S'),
                                "Uhrzeit des Fahrtendes": fahrt["Uhrzeit des Fahrtbeginns"].strftime('%H:%M:%S'),
                                "Kennzeichen": kennzeichen,
                                "Fahrername": fahrt["Fahrername"],
                                "Abholort": "PAUSE", "Zielort": "PAUSE", "Kilometer": 0,
                                "_TYPE": "PAUSE"
                            })
                            final_rows.append(pause_row)
                            schicht_dauer_min = 0 # Reset nach Pause

                        # Die echte Fahrt hinzufügen
                        f_dict = fahrt.to_dict()
                        f_dict["Uhrzeit des Fahrtbeginns"] = fahrt["Uhrzeit des Fahrtbeginns"].strftime('%H:%M:%S')
                        f_dict["Uhrzeit des Fahrtendes"] = fahrt["Uhrzeit des Fahrtendes"].strftime('%H:%M:%S')
                        f_dict["_TYPE"] = "REAL"
                        final_rows.append(f_dict)
                        
                        # Lücke zum nächsten Auftrag füllen (außer bei der letzten Fahrt)
                        if i < len(tag_group) - 1:
                            naechste_fahrt = tag_group.iloc[i+1]
                            luecke_min = (naechste_fahrt["Uhrzeit des Fahrtbeginns"] - fahrt["Uhrzeit des Fahrtendes"]).total_seconds() / 60
                            if luecke_min > 1:
                                leer = {c: "" for c in WUNSCH_SPALTEN}
                                leer.update({
                                    "Datum der Fahrt": tag,
                                    "Uhrzeit des Fahrtbeginns": fahrt["Uhrzeit des Fahrtendes"].strftime('%H:%M:%S'),
                                    "Uhrzeit des Fahrtendes": naechste_fahrt["Uhrzeit des Fahrtbeginns"].strftime('%H:%M:%S'),
                                    "Kennzeichen": kennzeichen,
                                    "Fahrername": fahrt["Fahrername"],
                                    "Abholort": fahrt["Zielort"],
                                    "Zielort": naechste_fahrt["Abholort"],
                                    "Kilometer": round(luecke_min * (speed_kmh / 60), 2),
                                    "_TYPE": "TRANSFER"
                                })
                                final_rows.append(leer)

                # Speichern
                res_df = pd.DataFrame(final_rows)
                sheet_name = str(kennzeichen)[:30]
                res_df[WUNSCH_SPALTEN].to_excel(writer, sheet_name=sheet_name, index=False)

        st.success("✅ Fertig! Erste Fahrt startet in Frechen, Pausen integriert.")
        st.download_button("Rechtssichere Excel herunterladen", data=output.getvalue(), file_name="Uber_Fahrtenbuch_Final.xlsx")
    except Exception as e:
        st.error(f"Fehler: {e}")
