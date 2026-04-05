import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel Logic Pro", layout="wide")

# --- UI ---
st.title("🚗 Taryel-Logik: Schichten & Standorte")
st.markdown(r"Bereinigt \N, simuliert Standorte und schließt Lücken.")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    speed_city = st.number_input("Schnitt KM/H", value=22)
    min_p = st.slider("Pause zw. Fahrten (Min)", 2, 5, 3)

uploaded_file = st.file_uploader("Rohdaten hochladen", type=["xlsx", "csv"])

# Spalten-Definition
FINAL_COLS = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", 
    "Datum der Fahrt", "Fahrtstatus", 
    "Standort des Fahrzeugs bei Auftragsuebermittlung", 
    "Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
    "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Einlesen
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
            
        df.columns = [str(c).strip() for c in df.columns]

        # 1. Nur abgeschlossene
        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]
        
        # 2. Zeit-Parsing
        d_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
                  "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
        for col in d_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Kennzeichen"])

        if not df.empty:
            output = io.BytesIO()
            orange = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df['Tag_Key'] = df['Uhrzeit des Fahrtbeginns'].dt.date
                
                for (tag, kennz, fahrer), group in df.groupby(['Tag_Key', 'Kennzeichen', 'Fahrername']):
                    group = group.sort_values("Uhrzeit des Fahrtbeginns")
                    rows = []
                    # Standard Köln Koordinate
                    last_loc = "50.9375 6.9603" 

                    for i in range(len(group)):
                        row = group.iloc[i].to_dict()
                        
                        # Standort-Spaltenname in Variable für Kürze
                        loc_col = "Standort des Fahrzeugs bei Auftragsuebermittlung"
                        
                        if i == 0:
                            val = str(row.get(loc_col, ""))
                            if "\\N" in val or "nan" in val.lower() or not val.strip():
                                row[loc_col] = last_loc
                            else:
                                last_loc = val
                            rows.append(row)
                            continue

                        # Anschluss-Logik
                        prev = rows[-1]
                        prev_e = prev["Uhrzeit des Fahrtendes"]
                        
                        # Standort = Letztes Ziel / Letzte Position
                        row[loc_col] = last_loc

                        # Zeiten rücken zusammen
                        wait = random.randint(min_p, min_p + 2)
                        new_a = prev_e + timedelta(minutes=wait)
                        new_s = new_a + timedelta(minutes=random.randint(3, 6))
                        
                        dur = row["Uhrzeit des Fahrtendes"] - row["Uhrzeit des Fahrtbeginns"]
                        
                        row["Datum/Uhrzeit Auftragseingang"] = new_a - timedelta(seconds=30)
                        row["Uhrzeit der Auftragsuebermittlung"] = new_a
                        row["Uhrzeit des Fahrtbeginns"] = new_s
                        row["Uhrzeit des Fahrtendes"] = new_s + dur
                        
                        # KM-Anpassung
                        orig_s = group.iloc[i]["Uhrzeit des Fahrtbeginns"]
                        gap_min = (orig_s - new_s).total_seconds() / 60
                        
                        if gap_min > 0:
                            bonus = round(gap_min * (speed_city / 60), 2)
                            try:
                                row["Kilometer"] = round(float(row.get("Kilometer", 0)) + bonus, 2)
                            except:
                                row["Kilometer"] = bonus

                        row["_CORR"] = True
                        rows.append(row)

                    # Export
                    res_df = pd.DataFrame(rows)
                    for c in d_cols:
                        if c in res_df.columns:
                            res_df[c] = pd.to_datetime(res_df[c]).dt.strftime('%Y-%m-%d %H:%M:%S')

                    s_name = f"{tag}_{fahrer[:10]}".replace("/", "")[:31]
                    res_df[FINAL_COLS].to_excel(writer, sheet_name=s_name, index=False)
                    
                    ws = writer.sheets[s_name]
                    for idx, r_d in enumerate(rows, start=2):
                        if r_d.get("_CORR"):
                            for c_idx in range(1, len(FINAL_COLS) + 1):
                                ws.cell(row=idx, column=c_idx).fill = orange

            st.success("✅ Fertig! Struktur korrigiert.")
            st.download_button("Download", data=output.getvalue(), file_name="Uber_Taryel_Style.xlsx")
            
    except Exception as e:
        st.error(f"Fehler: {e}")
