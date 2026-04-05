import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Taryel-Logic Ultimate (Grün)", layout="wide")

# --- UI MASKE ---
st.title("🚗 Taryel-Automator: Das 'Grüne' Ergebnis")
st.markdown("Erstellt eine lückenlose, gesetzeskonforme Schicht aus Uber-Rohdaten.")

with st.sidebar:
    st.header("📍 Stammdaten")
    bs_adresse = st.text_input("Betriebssitz (Start/Ende)", "Otto-Klein-Straße 24, 50858 Köln")
    st.header("⏱️ Schicht & Pausen")
    work_goal = st.slider("Ziel-Schichtdauer (Stunden)", 6, 12, 8)
    break_duration = st.slider("Gesetzliche Pause (Minuten)", 30, 60, 45)
    speed_city = st.number_input("Schnitt KM/H (Anfahrt)", value=22)

uploaded_file = st.file_uploader("test.xlsx hochladen", type=["xlsx", "csv"])

# Ziel-Spalten wie im Taryel-Muster
FINAL_COLUMNS = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Laden & Filtern
        df = pd.read_csv(uploaded_file, sep=None, engine='python') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Nur grüne (abgeschlossene) Fahrten
        df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]
        
        # Datetime Konvertierung
        for col in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang"]:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Kennzeichen"])

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Gruppierung nach Tag & Fahrer
            df['Tag'] = df['Uhrzeit des Fahrtbeginns'].dt.date
            
            for (tag, kennzeichen, fahrer), group in df.groupby(['Tag', 'Kennzeichen', 'Fahrername']):
                group = group.sort_values("Uhrzeit des Fahrtbeginns")
                final_rows = []
                schicht_start_zeit = group.iloc[0]["Uhrzeit des Fahrtbeginns"]
                
                for i in range(len(group)):
                    row = group.iloc[i].to_dict()
                    row["_CORRECTED"] = False
                    
                    if i > 0:
                        prev_ende = final_rows[i-1]["Uhrzeit des Fahrtendes"]
                        curr_start_orig = row["Uhrzeit des Fahrtbeginns"]
                        
                        # Check: Ist eine gesetzliche Pause fällig? (Nach 6 Std Schicht)
                        stunden_seit_start = (prev_ende - schicht_start_zeit).total_seconds() / 3600
                        
                        # Falls Schicht > 6h und noch keine Pause gemacht wurde
                        gap_min = random.randint(3, 6) # Standard-Puffer
                        if stunden_seit_start > 6 and i == len(group) // 2: 
                            gap_min = break_duration # Große gesetzliche Pause einfügen
                        
                        new_start = prev_ende + timedelta(minutes=gap_min)
                        
                        # Zeiten anpassen (Menschliche Kette)
                        row["Datum/Uhrzeit Auftragseingang"] = new_start - timedelta(minutes=random.randint(1, 3))
                        row["Uhrzeit der Auftragsuebermittlung"] = row["Datum/Uhrzeit Auftragseingang"] + timedelta(seconds=15)
                        row["Uhrzeit des Fahrtbeginns"] = new_start
                        
                        # KM-Simulation (Nur wenn keine große Pause war)
                        if gap_min < break_duration:
                            zeit_diff = (curr_start_orig - new_start).total_seconds() / 60
                            if zeit_diff > 0:
                                extra_km = round(zeit_diff * (speed_city / 60), 2)
                                row["Kilometer"] = round(float(row["Kilometer"]) + extra_km, 2)
                        
                        row["_CORRECTED"] = True
                    
                    final_rows.append(row)

                # Export & Styling
                res_df = pd.DataFrame(final_rows)
                for c in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]:
                    res_df[c] = pd.to_datetime(res_df[c]).dt.strftime('%Y-%m-%d %H:%M:%S')

                sheet_name = f"{tag}_{fahrer[:10]}"
                res_df[FINAL_COLUMNS].to_excel(writer, sheet_name=sheet_name, index=False)
                
                ws = writer.sheets[sheet_name]
                for idx, r_data in enumerate(final_rows, start=2):
                    if r_data["_CORRECTED"]:
                        for c_idx in range(1, len(FINAL_COLUMNS) + 1):
                            ws.cell(row=idx, column=c_idx).fill = orange_fill

        st.success("✅ 'Grüne' Auswertung fertiggestellt (Inkl. Pausen-Logik).")
        st.download_button("Taryel-Ergebnis (Grün) herunterladen", data=output.getvalue(), file_name="Taryel_Grün_Ergebnis.xlsx")

    except Exception as e:
        st.error(f"Fehler: {e}")
