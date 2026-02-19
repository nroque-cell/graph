import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from googleapiclient.discovery import build
from google.oauth2 import service_account

st.set_page_config(layout="wide")

PALETA_EMPRESAS = [
    "#2563eb",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#06b6d4",
    "#84cc16",
    "#ec4899",
    "#f97316",
    "#14b8a6",
    "#6366f1"
]

SHEET_ID = st.secrets["sheet_id"]

credenciales = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)

planilla = build("sheets", "v4", credentials=credenciales).spreadsheets()


@st.cache_data(ttl=600)
def cargar_resumen():

    resultado = planilla.values().get(
        spreadsheetId=SHEET_ID,
        range="RESUMEN DIARIO!A:Z",
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    valores = resultado.get("values", [])
    df = pd.DataFrame(valores[1:], columns=valores[0])

    df.columns = df.columns.str.strip().str.upper()

    df["FECHA"] = pd.to_datetime(df["FECHA"])
    df["SEMANA"] = pd.to_numeric(df["SEMANA"])
    df["CANTIDAD"] = pd.to_numeric(df["CANTIDAD"])
    df["PAGO"] = pd.to_numeric(df["PAGO"])

    return df


@st.cache_data(ttl=600)
def cargar_volumen():

    resultado = planilla.values().get(
        spreadsheetId=SHEET_ID,
        range="VOLUMEN PROPORCIONAL!A:Z",
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    valores = resultado.get("values", [])
    df = pd.DataFrame(valores[1:], columns=valores[0])

    df.columns = df.columns.str.strip().str.upper()
    df["MES"] = pd.to_numeric(df["MES"], errors="coerce")

    for col in df.columns:
        if "DIARIO" in col:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


df_resumen = cargar_resumen()
df_volumen = cargar_volumen()

tab1, tab2 = st.tabs(["DIARIO", "SEMANAL"])


with tab1:

    turnos = st.multiselect(
        "Filtrar Turno",
        df_resumen["TURNO"].unique(),
        default=df_resumen["TURNO"].unique()
    )

    df = df_resumen[
        (df_resumen["CARGO"] == "PICKEADOR") &
        (df_resumen["TURNO"].isin(turnos))
    ]

    cajas_diarias = df.groupby(
        ["FECHA", "EMPRESA"]
    )["CANTIDAD"].sum().reset_index()

    fig = go.Figure()

    for i, empresa in enumerate(cajas_diarias["EMPRESA"].unique()):

        df_emp = cajas_diarias[
            cajas_diarias["EMPRESA"] == empresa
        ]

        fig.add_trace(go.Bar(
            x=df_emp["FECHA"],
            y=df_emp["CANTIDAD"],
            name=empresa,
            marker_color=PALETA_EMPRESAS[i % len(PALETA_EMPRESAS)]
        ))

    mes_actual = cajas_diarias["FECHA"].dt.month.mode()[0]
    volumen_mes = df_volumen[df_volumen["MES"] == mes_actual]

    for col in volumen_mes.columns:
        if "DIARIO" in col:

            empresa = col.replace("DIARIO ", "")
            meta = volumen_mes[col].iloc[0]

            fechas = cajas_diarias["FECHA"].unique()

            fig.add_trace(go.Scatter(
                x=fechas,
                y=[meta]*len(fechas),
                mode="lines",
                name=f"Meta {empresa}",
                line=dict(
                    dash="dash",
                    width=3
                )
            ))

    fig.update_layout(
        title="Cajas Pickeadas por Día",
        barmode="group"
    )

    st.plotly_chart(fig, use_container_width=True)


with tab2:

    turnos = st.multiselect(
        "Filtrar Turno Semanal",
        df_resumen["TURNO"].unique(),
        default=df_resumen["TURNO"].unique(),
        key="turno_sem"
    )

    df = df_resumen[
        (df_resumen["CARGO"] == "PICKEADOR") &
        (df_resumen["TURNO"].isin(turnos))
    ]

    cajas_semanales = df.groupby(
        ["SEMANA", "EMPRESA"]
    )["CANTIDAD"].sum().reset_index()

    fig2 = go.Figure()

    for i, empresa in enumerate(cajas_semanales["EMPRESA"].unique()):

        df_emp = cajas_semanales[
            cajas_semanales["EMPRESA"] == empresa
        ]

        fig2.add_trace(go.Bar(
            x=df_emp["SEMANA"].astype(str),
            y=df_emp["CANTIDAD"],
            name=empresa,
            marker_color=PALETA_EMPRESAS[i % len(PALETA_EMPRESAS)]
        ))

    mes_actual = pd.Timestamp.today().month
    volumen_mes = df_volumen[df_volumen["MES"] == mes_actual]

    for col in volumen_mes.columns:
        if "DIARIO" in col:

            empresa = col.replace("DIARIO ", "")
            meta = volumen_mes[col].iloc[0] * 6

            semanas = cajas_semanales["SEMANA"].astype(str).unique()

            fig2.add_trace(go.Scatter(
                x=semanas,
                y=[meta]*len(semanas),
                mode="lines",
                name=f"Meta Semanal {empresa}",
                line=dict(
                    dash="dash",
                    width=3
                )
            ))

    fig2.update_layout(
        title="Cajas Pickeadas por Semana",
        barmode="group"
    )

    st.plotly_chart(fig2, use_container_width=True)
