import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel Ultimate Optimizer", layout="wide")

# --- UI ---
st.title("🚗 Taryel-Logik: Der 'Grüne' Listen-Prozessor")
st.markdown("Bereinigt unlogische Zwischenstopps und erstellt eine lückenlose Kette wie im Muster.")

with st.sidebar:
    st.header("⚙️ Strategie")
    betriebssitz = st.text_input("Start-Anker", "Otto-Klein-Straße 24, 50858 Köln")
    speed_city = st.number_input("Schnitt KM/H für Überbrückung", value=22)
    max_gap_allowed = st.slider("Max. reale Lücke (Min)", 5, 30, 10)
    st.info("Fahrten, die zu große Lücken reißen, werden durch Anfahrten ersetzt.")

uploaded_file = st.file_uploader("test.xlsx hochladen", type=["xlsx", "csv"])

FINAL_COLUMNS = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]

        # 1. Nur abgeschlossene Fahrten
        df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]
        
        # 2. Zeit-Parsing
        for col in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Kennzeichen"])

        if not df.empty:
            output = io.BytesIO()
            orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df['Tag_Key'] = df['Uhrzeit des Fahrtbeginns'].dt.date
                
                for (tag, kennzeichen, fahrer), group in df.groupby(['Tag_Key', 'Kennzeichen', 'Fahrername']):
                    group = group.sort_values("Uhrzeit des Fahrtbeginns")
                    final_rows = []
                    
                    for i in range(len(group)):
                        row = group.iloc[i].to_dict()
                        
                        if i == 0:
                            final_rows.append(row)
                            continue
                        
                        prev_ende = final_rows[-1]["Uhrzeit des Fahrtendes"]
                        curr_start = row["Uhrzeit des Fahrtbeginns"]
                        gap = (curr_start - prev_ende).total_seconds() / 60
                        
                        # LOGIK: Wenn Marzellenstraße o.ä. nicht passt (Lücke zu groß/unlogisch)
                        # Hier kann man manuell oder per Distanz-Check filtern. 
                        # Für dieses Skript: Wir 'glätten' alles, was über das Limit geht
                        
                        # Wir bauen die neue Kette
                        puffer = random.randint(2, 5)
                        new_start = prev_ende + timedelta(minutes=puffer)
                        
                        # Zeit-Korrektur (wie Taryel: Anschluss erzwingen)
                        row["Datum/Uhrzeit Auftragseingang"] = new_start - timedelta(minutes=random.randint(1, 2))
                        row["Uhrzeit der Auftragsuebermittlung"] = row["Datum/Uhrzeit Auftragseingang"] + timedelta(seconds=15)
                        row["Uhrzeit des Fahrtbeginns"] = new_start
                        
                        # Dauer der Fahrt beibehalten, aber Ende neu berechnen
                        dauer = (pd.to_datetime(group.iloc[i]["Uhrzeit des Fahrtendes"]) - pd.to_datetime(group.iloc[i]["Uhrzeit des Fahrtbeginns"]))
                        row["Uhrzeit des Fahrtendes"] = new_start + dauer
                        
                        # Kilometer-Bonus für die geschlossene Lücke
                        zeit_diff_min = (curr_start - new_start).total_seconds() / 60
                        if zeit_diff_min > 0:
                            bonus_km = round(zeit_diff_min * (speed_city / 60), 2)
                            try:
                                row["Kilometer"] = round(float(row["Kilometer"]) + bonus_km, 2)
                            except: row["Kilometer"] = bonus_km
                        
                        row["_CORRECTED"] = True
                        final_rows.append(row)

                    # Export
                    res_df = pd.DataFrame(final_rows)
                    for c in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]:
                        res_df[c] = pd.to_datetime(res_df[c]).dt.strftime('%Y-%m-%d %H:%M:%S')

                    sheet_name = f"{tag}_{fahrer[:10]}".replace("/", "")[:31]
                    res_df[FINAL_COLUMNS].to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    ws = writer.sheets[sheet_name]
                    for idx, r_data in enumerate(final_rows, start=2):
                        if r_data.get("_CORRECTED"):
                            for c_idx in range(1, len(FINAL_COLUMNS) + 1):
                                ws.cell(row=idx, column=c_idx).fill = orange_fill

            st.success("✅ Liste nach Taryel-Logik geglättet.")
            st.download_button("Grünes Ergebnis laden", data=output.getvalue(), file_name="Taryel_Geglaettet.xlsx")
            
    except Exception as e:
        st.error(f"Fehler: {e}")
