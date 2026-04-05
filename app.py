import streamlit as st
import pandas as pd
import io
import random
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Schicht-Master Pro", layout="wide")

# --- UI MASKE ---
st.title("🚗 Taryel-Logik: Der Schicht-Generator")
st.markdown("Erstellt aus der Rohliste eine saubere, grüne Auswertung inkl. Pausen.")

with st.sidebar:
    st.header("🏢 Stammdaten")
    betriebssitz = st.text_input("Betriebssitz (Start/Ende)", "Otto-Klein-Straße 24, 50858 Köln")
    st.header("⚙️ Parameter")
    speed_city = st.number_input("Schnitt KM/H für Anfahrten", value=22)
    pause_min = st.slider("Gesetzliche Pause (Min)", 30, 60, 45)

uploaded_file = st.file_uploader("test.xlsx hochladen", type=["xlsx", "csv"])

# Spalten-Definition für das grüne Ergebnis (Taryel-Style)
FINAL_COLUMNS = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
    "Uhrzeit des Fahrtendes", "Kennzeichen", "Fahrzeugtyp", "Fahrername", 
    "Fahrpreis", "Kilometer", "Abholort", "Zielort"
]

if uploaded_file:
    try:
        # Einlesen der Datei
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        
        # Spaltennamen säubern
        df.columns = [str(c).strip() for c in df.columns]

        # 1. SCHRITT: NUR DIE GRÜNEN (ABGESCHLOSSEN)
        if "Fahrtstatus" in df.columns:
            df = df[df["Fahrtstatus"].str.lower() == "abgeschlossen"]

        # 2. SCHRITT: DATUMSKORREKTUR (Löst das \N Problem)
        date_cols = ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes", 
                     "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung"]
        
        for col in date_cols:
            if col in df.columns:
                # 'coerce' wandelt \N in NaT um (Not a Time)
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Zeilen ohne Startzeit löschen
        df = df.dropna(subset=["Uhrzeit des Fahrtbeginns", "Kennzeichen"])

        if not df.empty:
            output = io.BytesIO()
            orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Korrekter Zugriff auf das Datum für die Gruppierung
                df['Tag_Key'] = df['Uhrzeit des Fahrtbeginns'].dt.date
                
                # Gruppierung nach Tag, Fahrzeug und Fahrer
                for (tag, kennzeichen, fahrer), group in df.groupby(['Tag_Key', 'Kennzeichen', 'Fahrername']):
                    group = group.sort_values("Uhrzeit des Fahrtbeginns")
                    final_rows = []
                    schicht_start = group.iloc[0]["Uhrzeit des Fahrtbeginns"]
                    
                    for i in range(len(group)):
                        row = group.iloc[i].to_dict()
                        row["_CORRECTED"] = False
                        
                        if i > 0:
                            prev_ende = final_rows[i-1]["Uhrzeit des Fahrtendes"]
                            orig_start = row["Uhrzeit des Fahrtbeginns"]
                            
                            # Zeit seit Schichtbeginn berechnen
                            stunden_aktiv = (prev_ende - schicht_start).total_seconds() / 3600
                            
                            # Standard Lücke (2-5 Min)
                            gap = random.randint(2, 5)
                            
                            # Wenn Schicht > 6h, einmalig Pause einbauen
                            pause_schon_gemacht = any("nach Pause" in str(r.get("Fahrtstatus", "")) for r in final_rows)
                            if stunden_aktiv > 6 and not pause_schon_gemacht:
                                gap = pause_min
                                row["Fahrtstatus"] = "abgeschlossen (nach Pause)"
                            
                            new_start = prev_ende + timedelta(minutes=gap)
                            
                            # Zeitkette anpassen
                            row["Datum/Uhrzeit Auftragseingang"] = new_start - timedelta(minutes=random.randint(1, 3))
                            row["Uhrzeit der Auftragsuebermittlung"] = row["Datum/Uhrzeit Auftragseingang"] + timedelta(seconds=15)
                            row["Uhrzeit des Fahrtbeginns"] = new_start
                            
                            # Kilometer anpassen (Simulation der Anfahrt)
                            zeit_diff_min = (orig_start - new_start).total_seconds() / 60
                            if zeit_diff_min > 0:
                                try:
                                    original_km = float(row.get("Kilometer", 0))
                                except:
                                    original_km = 0
                                row["Kilometer"] = round(original_km + (zeit_diff_min * (speed_city / 60)), 2)
                            
                            row["_CORRECTED"] = True
                        
                        final_rows.append(row)

                    # Zurück in DataFrame
                    res_df = pd.DataFrame(final_rows)
                    for c in date_cols:
                        if c in res_df.columns:
                            res_df[c] = pd.to_datetime(res_df[c]).dt.strftime('%Y-%m-%d %H:%M:%S')

                    # Sheet-Name generieren (max 31 Zeichen für Excel)
                    sheet_name = f"{tag}_{fahrer[:10]}".replace(":", "").replace("/", "")[:31]
                    res_df[FINAL_COLUMNS].to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Orange Markierung nur für geänderte Zeilen
                    ws = writer.sheets[sheet_name]
                    for idx, r_data in enumerate(final_rows, start=2):
                        if r_data["_CORRECTED"]:
                            for c_idx in range(1, len(FINAL_COLUMNS) + 1):
                                ws.cell(row=idx, column=c_idx).fill = orange_fill

            st.success("✅ 'Grüne' Auswertung erfolgreich erstellt!")
            st.download_button("Optimierte Liste herunterladen", data=output.getvalue(), file_name="Uber_Taryel_Style_Final.xlsx")
        else:
            st.warning("Keine abgeschlossenen Fahrten gefunden.")

    except Exception as e:
        st.error(f"Kritischer Fehler: {e}")
