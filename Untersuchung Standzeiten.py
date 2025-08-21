# Standzeiten-Analyse-Tool (Streamlit)

import streamlit as st
import pandas as pd
import plotly.express as px
import urllib.request

# --- Seitenkonfiguration ---
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
            response = urllib.request.urlopen(source)
            df = pd.read_excel(response, engine='openpyxl')
        else:
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
df['Standzeit_h'] = (df['Beendet'] - df['Gestartet']).dt.total_seconds() / 3600

# --- ERWEITERTE BERECHNUNG für Minuten und Stunden über 30 Min ---

# 1. Gesamte Standzeit jedes Vorgangs in Minuten berechnen.
df['Standzeit_min_gesamt'] = df['Standzeit_h'] * 60

# 2. Minuten über 30 berechnen. Negative Werte (für Ladevorgänge <= 30 Min) werden auf 0 gesetzt.
df['Min_Stand'] = (df['Standzeit_min_gesamt'] - 30).clip(lower=0)

# 3. NEU: Die Minuten über 30 in Stunden umrechnen für eine zusätzliche Kennzahl.
df['Std_Stand'] = df['Min_Stand'] / 60

# --- Ende der erweiterten Berechnung ---


# Negative oder Null-Standzeiten herausfiltern
df = df[df['Standzeit_h'] > 0.01]

# Erstellung der Monatsspalte für die spätere Gruppierung
df['Monat'] = df['Beendet'].dt.to_period('M').dt.to_timestamp()


# Schritt 3: Filter in der Seitenleiste
st.sidebar.header("🔎 Filteroptionen")

min_date = df['Beendet'].min().date()
max_date = df['Beendet'].max().date()
date_range = st.sidebar.date_input(
    "Zeitraum auswählen",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    help="Wählen Sie den Start- und Endzeitpunkt für die Analyse."
)

standorte = sorted(df['Standortname'].dropna().unique())
selected_standorte = st.sidebar.multiselect(
    "📍 Standort(e) auswählen",
    options=standorte,
    default=standorte,
    help="Wählen Sie einen oder mehrere Standorte aus, die in die Analyse einbezogen werden sollen."
)

if len(date_range) != 2:
    st.sidebar.error("Bitte einen gültigen Zeitraum mit Start- und Enddatum auswählen.")
    st.stop()

start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

df_filtered = df[
    (df['Beendet'] >= start_date) &
    (df['Beendet'] < (end_date + pd.Timedelta(days=1))) &
    (df['Standortname'].isin(selected_standorte))
]

if df_filtered.empty:
    st.warning("Für die gewählte Filterkombination sind keine Daten vorhanden. Bitte passen Sie die Filter an.")
    st.stop()


# Schritt 4: Aggregation und Visualisierung der Standzeiten
st.header("Monatliche Auswertung der Standzeiten")

# ERWEITERTE Aggregation: Nun auch mit 'Std_Stand'
standzeiten_pro_monat = df_filtered.groupby('Monat').agg(
    Gesamt_Standzeit_h=('Standzeit_h', 'sum'),
    Durchschnittl_Standzeit_h=('Standzeit_h', 'mean'),
    Anzahl_Vorgange=('Standzeit_h', 'count'),
    Gesamt_Min_Stand=('Min_Stand', 'sum'),
    Gesamt_Std_Stand=('Std_Stand', 'sum') # NEU
).reset_index()

# Runden der Ergebnisse
standzeiten_pro_monat['Gesamt_Standzeit_h'] = standzeiten_pro_monat['Gesamt_Standzeit_h'].round(2)
standzeiten_pro_monat['Durchschnittl_Standzeit_h'] = standzeiten_pro_monat['Durchschnittl_Standzeit_h'].round(2)
standzeiten_pro_monat['Gesamt_Min_Stand'] = standzeiten_pro_monat['Gesamt_Min_Stand'].round(2)
standzeiten_pro_monat['Gesamt_Std_Stand'] = standzeiten_pro_monat['Gesamt_Std_Stand'].round(2) # NEU


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
fig_standzeit_sum.update_layout(xaxis_tickformat="%b %Y")
st.plotly_chart(fig_standzeit_sum, use_container_width=True)


# --- NEU: Visualisierung 2 für 'Std_Stand' in Stunden ---
st.subheader("Gesamte Standzeit über 30 Minuten (in Stunden)")
fig_std_stand_sum = px.bar(
    standzeiten_pro_monat,
    x='Monat',
    y='Gesamt_Std_Stand',
    title='Summe der Standzeit-Stunden nach Abzug der ersten 30 Minuten pro Vorgang',
    labels={'Gesamt_Std_Stand': 'Gesamte "Überliegezeit" [Stunden]', 'Monat': 'Monat'},
    text='Gesamt_Std_Stand'
)
fig_std_stand_sum.update_traces(textposition='outside', marker_color='#d62728') # Neue Farbe zur Unterscheidung
fig_std_stand_sum.update_layout(xaxis_tickformat="%b %Y")
st.plotly_chart(fig_std_stand_sum, use_container_width=True)
# --- Ende des neuen Blocks ---


# Visualisierung 3: für 'Min_Stand' in Minuten
st.subheader("Gesamte Standzeit über 30 Minuten (in Minuten)")
fig_min_stand_sum = px.bar(
    standzeiten_pro_monat,
    x='Monat',
    y='Gesamt_Min_Stand',
    title='Summe der Standzeit-Minuten nach Abzug der ersten 30 Minuten pro Vorgang',
    labels={'Gesamt_Min_Stand': 'Gesamte "Überliegezeit" [Minuten]', 'Monat': 'Monat'},
    text='Gesamt_Min_Stand'
)
fig_min_stand_sum.update_traces(textposition='outside', marker_color='#2ca02c')
fig_min_stand_sum.update_layout(xaxis_tickformat="%b %Y")
st.plotly_chart(fig_min_stand_sum, use_container_width=True)


# Visualisierung 4: Durchschnittliche Standzeit pro Monat (Liniendiagramm)
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


# Visualisierung 5: Detaillierte Datentabelle (ERWEITERT)
st.subheader("Datentabelle der monatlichen Standzeit-KPIs")
st.dataframe(
    standzeiten_pro_monat.rename(columns={
        'Monat': 'Monat',
        'Gesamt_Standzeit_h': 'Gesamte Standzeit (Stunden)',
        'Durchschnittl_Standzeit_h': 'Ø Standzeit pro Vorgang (Stunden)',
        'Anzahl_Vorgange': 'Anzahl Ladevorgänge',
        'Gesamt_Min_Stand': 'Gesamte Zeit > 30 Min (Minuten)',
        'Gesamt_Std_Stand': 'Gesamte Zeit > 30 Min (Stunden)' # NEU
    }).style.format({
        'Monat': lambda t: t.strftime('%Y-%m'),
        'Gesamte Standzeit (Stunden)': '{:.2f}',
        'Ø Standzeit pro Vorgang (Stunden)': '{:.2f}',
        'Gesamte Zeit > 30 Min (Minuten)': '{:.2f}',
        'Gesamte Zeit > 30 Min (Stunden)': '{:.2f}' # NEU
    }),
    use_container_width=True
)
