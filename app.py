import streamlit as st
import pandas as pd
import io
from datetime import timedelta
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Uber Logik Korrektur-Modus", layout="wide")
st.title("🚗 Fahrtenbuch-Optimierung (Keine Zusatzzeilen)")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    speed_kmh = st.number_input("Schnitt-KM/H für die Zeitüberbrückung", value=20)
    st.info("Logik: Der Fahrtbeginn wird nach vorne gezogen, um Lücken zu schließen. Korrigierte Zeilen werden orange.")

uploaded_file = st.file_uploader("Uber Liste hochladen (z.B. test.xlsx)", type=["xlsx", "csv"])

ALLE_SPALTEN = [
    "Datum/Uhrzeit Auftragseingang", "Uhrzeit der Auftragsuebermittlung", "Datum der Fahrt", 
    "Fahrtstatus", "Standort des Fahrzeugs bei Auftragsuebermittlung", "Uhrzeit des Fahrtbeginns", 
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
        
        # Zeit-Konvertierung
        df["Uhrzeit des Fahrtbeginns"] = pd.to_datetime(df["Uhrzeit des Fahrtbeginns"], errors='coerce')
        df["Uhrzeit des Fahrtendes"] = pd.to_datetime(df["Uhrzeit des Fahrtendes"], errors='coerce')
        df = df.dropna(subset=["Kennzeichen", "Uhrzeit des Fahrtbeginns"])

        output = io.BytesIO()
        orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for kennzeichen, k_group in df.groupby("Kennzeichen"):
                k_group = k_group.sort_values("Uhrzeit des Fahrtbeginns")
                final_rows = []
                
                # Wir gehen die Fahrten durch und ziehen die Zeiten zusammen
                for i in range(len(k_group)):
                    current = k_group.iloc[i].to_dict()
                    is_corrected = False
                    
                    if i > 0:
                        prev_ende = final_rows[i-1]["Uhrzeit des Fahrtendes"]
                        this_start = current["Uhrzeit des Fahrtbeginns"]
                        
                        # Wenn eine Lücke von mehr als 1 Minute existiert
                        if this_start > prev_ende + timedelta(minutes=1):
                            diff_min = (this_start - prev_ende).total_seconds() / 60
                            # Kilometer für die Lücke berechnen
                            extra_km = round(diff_min * (speed_kmh / 60), 2)
                            
                            # KORREKTUR: Startzeit auf das Ende der letzten Fahrt setzen
                            current["Uhrzeit des Fahrtbeginns"] = prev_ende
                            # Kilometer erhöhen (Original + Anfahrt)
                            try:
                                current["Kilometer"] = float(current["Kilometer"]) + extra_km
                            except:
                                current["Kilometer"] = extra_km
                            
                            current["Fahrtstatus"] = "Anfahrt + Auftrag"
                            is_corrected = True
                    
                    # Zeit für die Ausgabe formatieren
                    current["_IS_CORRECTED"] = is_corrected
                    final_rows.append(current)

                # Zurück in DataFrame und Formatierung
                res_df = pd.DataFrame(final_rows)
                
                # Datumsobjekte für Excel-Export in Strings wandeln
                for col in ["Uhrzeit des Fahrtbeginns", "Uhrzeit des Fahrtendes"]:
                    res_df[col] = res_df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                
                sheet_name = str(kennzeichen)[:30]
                res_df[ALLE_SPALTEN].to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Styling
                ws = writer.sheets[sheet_name]
                for idx, row_data in enumerate(final_rows, start=2):
                    if row_data["_IS_CORRECTED"]:
                        for col_idx in range(1, len(ALLE_SPALTEN) + 1):
                            ws.cell(row=idx, column=col_idx).fill = orange_fill

        st.success("✅ Optimierung abgeschlossen. Lücken wurden in die Fahrten integriert.")
        st.download_button("Optimierte Excel herunterladen", data=output.getvalue(), file_name="Uber_Optimiert_Lueckenlos.xlsx")
        
    except Exception as e:
        st.error(f"Fehler bei der Verarbeitung: {e}")
