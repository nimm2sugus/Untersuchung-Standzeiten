# Standzeiten-Analyse-Tool (Streamlit)

import streamlit as st
import pandas as pd
import plotly.express as px
import urllib.request

# --- Seitenkonfiguration ---
# Das sollte immer die erste Streamlit-Anweisung im Skript sein.
st.set_page_config(
    page_title="Analyse der Standzeiten",
    page_icon="⏱️",
    layout="wide"
)

# --- Funktionen ---

@st.cache_data
def load_excel_file(source, from_url=False):
    """
    Lädt eine Excel-Datei von einer lokalen Quelle oder einer URL.
    Verwendet Caching, um die Datei nicht bei jeder Interaktion neu laden zu müssen.
    """
    try:
        if from_url:
            # Datei von einer URL laden
            response = urllib.request.urlopen(source)
            df = pd.read_excel(response, engine='openpyxl')
        else:
            # Datei aus einem Upload laden
            df = pd.read_excel(source, engine='openpyxl')
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der Datei: {e}")
        return None

# --- Hauptprogramm ---
st.title("⏱️ Analyse der Standzeiten von Ladevorgängen")
st.markdown("Dieses Tool dient der Auswertung und Visualisierung der Standzeiten pro Monat basierend auf Ihren Ladedaten.")

# Schritt 1: Auswahl der Datenquelle
input_method = st.radio(
    "📂 Wählen Sie Ihre Datenquelle:",
    ["Datei-Upload", "Öffentlicher SharePoint-Link"],
    horizontal=True
)
df = None

if input_method == "Datei-Upload":
    uploaded_file = st.file_uploader("Laden Sie Ihre bereinigte Excel-Datei hoch", type=["xlsx", "xls"])
    if uploaded_file is not None:
        df = load_excel_file(uploaded_file)
        if df is not None:
            st.success("Datei erfolgreich hochgeladen und geladen.")

elif input_method == "Öffentlicher SharePoint-Link":
    sharepoint_url = st.text_input("Fügen Sie den öffentlichen Download-Link zur Excel-Datei ein", "")
    if sharepoint_url:
        if st.button("Daten von SharePoint laden"):
            df = load_excel_file(sharepoint_url, from_url=True)
            if df is not None:
                st.success("Datei erfolgreich von SharePoint geladen.")

# Wenn keine Daten geladen wurden, wird hier gestoppt.
if df is None:
    st.info("Bitte laden Sie eine Datei hoch oder geben Sie einen Link an, um die Analyse zu starten.")
    st.stop()


# Schritt 2: Datenaufbereitung und -validierung
df = df.copy()

# Überprüfung, ob die notwendigen Spalten vorhanden sind
expected_cols = ['Gestartet', 'Beendet', 'Standortname']
missing_cols = [col for col in expected_cols if col not in df.columns]
if missing_cols:
    st.error(f"Die folgenden erforderlichen Spalten fehlen in der Datei: {missing_cols}")
    st.stop()

# Datumsspalten konvertieren und Fehler behandeln
df['Gestartet'] = pd.to_datetime(df['Gestartet'], errors='coerce')
df['Beendet'] = pd.to_datetime(df['Beendet'], errors='coerce')

# Zeilen mit ungültigen Datumswerten entfernen
df.dropna(subset=['Gestartet', 'Beendet'], inplace=True)

# Berechnung der Standzeit (in Stunden)
# Die Standzeit ist hier als die gesamte Dauer von 'Gestartet' bis 'Beendet' definiert.
df['Standzeit_h'] = (df['Beendet'] - df['Gestartet']).dt.total_seconds() / 3600

# Negative oder Null-Standzeiten herausfiltern, da sie nicht plausibel sind
df = df[df['Standzeit_h'] > 0.01] # Ein kleiner Schwellenwert, um sehr kurze, irrelevante Sessions zu ignorieren

# Erstellung der Monatsspalte für die spätere Gruppierung
df['Monat'] = df['Beendet'].dt.to_period('M').dt.to_timestamp()


# Schritt 3: Filter in der Seitenleiste
st.sidebar.header("🔎 Filteroptionen")

# Zeitraum-Filter
min_date = df['Beendet'].min().date()
max_date = df['Beendet'].max().date()
date_range = st.sidebar.date_input(
    "Zeitraum auswählen",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    help="Wählen Sie den Start- und Endzeitpunkt für die Analyse."
)

# Standort-Filter
standorte = sorted(df['Standortname'].dropna().unique())
selected_standorte = st.sidebar.multiselect(
    "📍 Standort(e) auswählen",
    options=standorte,
    default=standorte,
    help="Wählen Sie einen oder mehrere Standorte aus, die in die Analyse einbezogen werden sollen."
)

# Sicherstellen, dass ein gültiger Zeitraum ausgewählt wurde
if len(date_range) != 2:
    st.sidebar.error("Bitte einen gültigen Zeitraum mit Start- und Enddatum auswählen.")
    st.stop()

# Anwenden der Filter auf den DataFrame
start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

df_filtered = df[
    (df['Beendet'] >= start_date) &
    # Das Enddatum wird auf das Ende des Tages gesetzt, um auch Ladevorgänge am letzten Tag zu erfassen
    (df['Beendet'] < (end_date + pd.Timedelta(days=1))) &
    (df['Standortname'].isin(selected_standorte))
]

# Überprüfen, ob nach der Filterung noch Daten vorhanden sind
if df_filtered.empty:
    st.warning("Für die gewählte Filterkombination sind keine Daten vorhanden. Bitte passen Sie die Filter an.")
    st.stop()


# Schritt 4: Aggregation und Visualisierung der Standzeiten
st.header("Monatliche Auswertung der Standzeiten")

# Datenaggregation: Gruppierung nach Monat und Berechnung der relevanten Kennzahlen
standzeiten_pro_monat = df_filtered.groupby('Monat').agg(
    Gesamt_Standzeit_h=('Standzeit_h', 'sum'),
    Durchschnittl_Standzeit_h=('Standzeit_h', 'mean'),
    Anzahl_Vorgange=('Standzeit_h', 'count')
).reset_index()

# Runden der Ergebnisse für eine saubere Darstellung
standzeiten_pro_monat['Gesamt_Standzeit_h'] = standzeiten_pro_monat['Gesamt_Standzeit_h'].round(2)
standzeiten_pro_monat['Durchschnittl_Standzeit_h'] = standzeiten_pro_monat['Durchschnittl_Standzeit_h'].round(2)

# Visualisierung 1: Gesamte Standzeit pro Monat (Balkendiagramm)
st.subheader("Gesamte monatliche Standzeit (in Stunden)")
fig_standzeit_sum = px.bar(
    standzeiten_pro_monat,
    x='Monat',
    y='Gesamt_Standzeit_h',
    title='Summe der Standzeiten pro Monat für ausgewählte Standorte',
    labels={'Gesamt_Standzeit_h': 'Gesamte Standzeit [h]', 'Monat': 'Monat'},
    text='Gesamt_Standzeit_h'
)
fig_standzeit_sum.update_traces(textposition='outside', marker_color='#1f77b4')
fig_standzeit_sum.update_layout(xaxis_tickformat="%b %Y") # Format z.B. "Aug 2025"
st.plotly_chart(fig_standzeit_sum, use_container_width=True)


# Visualisierung 2: Durchschnittliche Standzeit pro Monat (Liniendiagramm)
st.subheader("Durchschnittliche Standzeit pro Ladevorgang (in Stunden)")
fig_standzeit_avg = px.line(
    standzeiten_pro_monat,
    x='Monat',
    y='Durchschnittl_Standzeit_h',
    title='Trend der durchschnittlichen Standzeit pro Monat',
    labels={'Durchschnittl_Standzeit_h': 'Durchschnittliche Standzeit [h]', 'Monat': 'Monat'},
    markers=True
)
fig_standzeit_avg.update_traces(line_color='#ff7f0e')
fig_standzeit_avg.update_layout(xaxis_tickformat="%b %Y")
st.plotly_chart(fig_standzeit_avg, use_container_width=True)


# Visualisierung 3: Detaillierte Datentabelle
st.subheader("Datentabelle der monatlichen Standzeit-KPIs")
st.dataframe(
    standzeiten_pro_monat.rename(columns={
        'Monat': 'Monat',
        'Gesamt_Standzeit_h': 'Gesamte Standzeit (Stunden)',
        'Durchschnittl_Standzeit_h': 'Ø Standzeit pro Vorgang (Stunden)',
        'Anzahl_Vorgange': 'Anzahl Ladevorgänge'
    }).style.format({
        'Monat': lambda t: t.strftime('%Y-%m'), # Formatierung für die Tabellenansicht
        'Gesamte Standzeit (Stunden)': '{:.2f}',
        'Ø Standzeit pro Vorgang (Stunden)': '{:.2f}'
    }),
    use_container_width=True
)
