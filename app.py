import streamlit as st
import pandas as pd
import io
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Logik Color-Mode", layout="wide")
st.title("🚗 Fahrtenbuch-Generator (Original vs. Korrektur)")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    speed_kmh = st.number_input("Schnitt-KM/H für Leerzeiten", value=25)
    st.info("Weiß = Original Uber | Orange = Berechnete Korrektur")

uploaded_file = st.file_uploader("Uber Liste hochladen", type=["xlsx", "csv"])

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
        df["Uhrzeit des Fahrtbeginns"] = pd.to_datetime(df["Uhrzeit des Fahrtbeginns"], errors='coerce')
        df["Uhrzeit des Fahrtendes"] = pd.to_datetime(df["Uhrzeit des Fahrtendes"], errors='coerce')
        df = df.dropna(subset=["Kennzeichen", "Uhrzeit des Fahrtbeginns"])

        if not df.empty:
            output = io.BytesIO()
            # Definition der orangen Farbe
            orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for kennzeichen, k_group in df.groupby("Kennzeichen"):
                    k_group['Tag'] = k_group['Uhrzeit des Fahrtbeginns'].dt.date
                    final_rows_with_meta = [] # Speichert Zeile + Farb-Info

                    for tag, tag_group in k_group.groupby('Tag'):
                        tag_group = tag_group.sort_values("Uhrzeit des Fahrtbeginns")
                        
                        for i in range(len(tag_group)):
                            fahrt = tag_group.iloc[i]
                            f_start = fahrt["Uhrzeit des Fahrtbeginns"]
                            f_ende = fahrt["Uhrzeit des Fahrtendes"] if pd.notnull(fahrt["Uhrzeit des Fahrtendes"]) else f_start + timedelta(minutes=15)
                            
                            # 1. ECHTE FAHRT (WEISS)
                            f_dict = {c: fahrt.get(c, "") for c in ALLE_SPALTEN}
                            f_dict.update({
                                "Uhrzeit des Fahrtbeginns": f_start.strftime('%Y-%m-%d %H:%M:%S'),
                                "Uhrzeit des Fahrtendes": f_ende.strftime('%Y-%m-%d %H:%M:%S'),
                                "_IS_CORRECTION": False
                            })
                            final_rows_with_meta.append(f_dict)

                            # 2. LÜCKE FÜLLEN (ORANGE)
                            if i < len(tag_group) - 1:
                                naechste = tag_group.iloc[i+1]
                                n_start = naechste["Uhrzeit des Fahrtbeginns"]
                                luecke_min = (n_start - f_ende).total_seconds() / 60
                                
                                if luecke_min > 1:
                                    leer = {c: "" for c in ALLE_SPALTEN}
                                    leer.update({
                                        "Datum der Fahrt": tag,
                                        "Fahrtstatus": "Betriebsfahrt (Korrektur)",
                                        "Uhrzeit des Fahrtbeginns": f_ende.strftime('%Y-%m-%d %H:%M:%S'),
                                        "Uhrzeit des Fahrtendes": n_start.strftime('%Y-%m-%d %H:%M:%S'),
                                        "Kennzeichen": kennzeichen,
                                        "Fahrername": fahrt.get("Fahrername", ""),
                                        "Abholort": fahrt.get("Zielort", ""),
                                        "Zielort": naechste.get("Abholort", ""),
                                        "Kilometer": round(luecke_min * (speed_kmh / 60), 2),
                                        "Fahrpreis": 0,
                                        "_IS_CORRECTION": True
                                    })
                                    final_rows_with_meta.append(leer)

                    # DataFrame erstellen und Metadaten-Spalte für Excel-Styling nutzen
                    res_df = pd.DataFrame(final_rows_with_meta)
                    sheet_name = str(kennzeichen)[:30]
                    
                    # Nur die echten Spalten in Excel schreiben
                    res_df[ALLE_SPALTEN].to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Styling anwenden
                    ws = writer.sheets[sheet_name]
                    for row_idx, row_data in enumerate(final_rows_with_meta, start=2): # start=2 wegen Header
                        if row_data["_IS_CORRECTION"]:
                            for col_idx in range(1, len(ALLE_SPALTEN) + 1):
                                ws.cell(row=row_idx, column=col_idx).fill = orange_fill

            st.success("✅ Fertig! Originale sind weiß, Korrekturen sind orange markiert.")
            st.download_button("Excel mit Farbmarkierung herunterladen", data=output.getvalue(), file_name="Fahrtenbuch_Markiert.xlsx")
    except Exception as e:
        st.error(f"Fehler: {e}")
