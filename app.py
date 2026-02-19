

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import re
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHEET_ID = "1t5s_CuTUUj9pWFpBzrHirLUZXAr-sqm6nWUjjschDPQ"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
ARCHIVO_CUENTA = os.path.join(BASE_DIR, "gcp_key.json")

credenciales = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)

servicio = build("sheets", "v4", credentials=credenciales)
planilla = servicio.spreadsheets()


st.set_page_config(
    page_title="Dashboard Empresas",
    layout="wide"
)


st.markdown("""
<style>

/* ===========================
   FONDO GENERAL
=========================== */

.stApp {
    background-color: #f6fff8;
}


/* ===========================
   TABS
=========================== */

[data-testid="stTabs"] button {
    background-color: #dcfce7;
    color: #14532d;
    font-weight: 600;
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    margin-right: 4px;
    transition: all 0.2s ease;
}

[data-testid="stTabs"] button:hover {
    background-color: #bbf7d0;
    color: #052e16;
}

/* TAB ACTIVO */
[data-testid="stTabs"] button[aria-selected="true"] {
    background-color: #007A33 !important;
    color: white !important;
}


/* ===========================
   MULTISELECT
=========================== */

[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background-color: #16a34a !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 4px 10px;
}

[data-testid="stMultiSelect"] span[data-baseweb="tag"]:hover {
    background-color: #15803d !important;
}

[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {
    color: white !important;
}


/* ===========================
   SELECT BOX
=========================== */

div[data-baseweb="select"] {
    border-radius: 8px;
}


/* ===========================
   DIVIDER
=========================== */

hr {
    border-color: #bbf7d0;
}


/* ===========================
   TITULOS
=========================== */

h1, h2, h3 {
    color: #14532d;
}

</style>
""", unsafe_allow_html=True)



@st.cache_data(ttl=600)
def cargar_datos_semanal():

    resultado = planilla.values().get(
        spreadsheetId=SHEET_ID,
        range="DASHBOARD SEMANAL!A:Z",
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    valores = resultado.get("values", [])
    if len(valores) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(valores[1:], columns=valores[0])
    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "_")

    for col in ["TOTAL_GENERAL","PPTO_SEMANAL","SEMANA"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df[df["SEMANA"] != 0]
    df["SEMANA"] = df["SEMANA"].astype(int)

    return df


@st.cache_data(ttl=600)
def cargar_datos_diario():

    resultado = planilla.values().get(
        spreadsheetId=SHEET_ID,
        range="DASHBOARD DIARIO!A:Z",
        valueRenderOption="FORMATTED_VALUE"
    ).execute()

    valores = resultado.get("values", [])
    if len(valores) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(valores[1:], columns=valores[0])
    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "_")

    for col in ["PAGO_REAL","PPTO_DIARIO"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[^0-9.]", "", regex=True)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["FECHA"] = pd.to_datetime(
        df["FECHA"],
        dayfirst=True,
        errors="coerce"
    )

    df = df[df["FECHA"].notna()]

    return df


@st.cache_data(ttl=600)
def cargar_resumen_diario():

    resultado = planilla.values().get(
        spreadsheetId=SHEET_ID,
        range="RESUMEN DIARIO!A:Z",
        valueRenderOption="UNFORMATTED_VALUE"
    ).execute()

    valores = resultado.get("values", [])
    if len(valores) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(valores[1:], columns=valores[0])
    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "_")

    df["FECHA"] = pd.to_numeric(df["FECHA"], errors="coerce")

    df["FECHA"] = pd.to_datetime(
        df["FECHA"],
        unit="D",
        origin="1899-12-30"
    )

    df = df[df["FECHA"].notna()]
    df["SEMANA"] = df["SEMANA"].astype(int)

    return df



tab1, tab2 = st.tabs(["Semanal","Diario"])



with tab1:
    df_semanal = cargar_datos_semanal()

    if df_semanal.empty:
        st.warning("No se encontraron datos en DASHBOARD SEMANAL")
    else:
        turnos = sorted(df_semanal["TURNO"].dropna().unique())
        turno_sel = st.multiselect(
            "Filtrar Turno",
            options=turnos,
            default=turnos,
            key="turno_semanal"
        )

        df_semanal = df_semanal[df_semanal["TURNO"].isin(turno_sel)]

        df_semanal["TIPO"] = df_semanal["EMPRESA"].str.contains(
            "picking", case=False, na=False
        ).map({True: "Picking", False: "Trafico/Bodega"})

        total_empresas = df_semanal.groupby(
            ["SEMANA","EMPRESA"]
        )["TOTAL_GENERAL"].sum().reset_index()

        presupuesto_tipo = df_semanal.groupby(
            ["SEMANA","TIPO"]
        )["PPTO_SEMANAL"].first().reset_index()

        fig = go.Figure()

        for empresa in total_empresas["EMPRESA"].unique():
            df_emp = total_empresas[total_empresas["EMPRESA"] == empresa]

            fig.add_trace(go.Bar(
                x=df_emp["SEMANA"].astype(str),
                y=df_emp["TOTAL_GENERAL"],
                name=empresa,
                hovertemplate="%{y:,.0f} M"
            ))

        for tipo in presupuesto_tipo["TIPO"].unique():
            df_pp = presupuesto_tipo[presupuesto_tipo["TIPO"] == tipo]

            fig.add_trace(go.Scatter(
                x=df_pp["SEMANA"].astype(str),
                y=df_pp["PPTO_SEMANAL"],
                mode="lines+markers",
                name=f"Presupuesto {tipo}",
                line=dict(width=3),
                hovertemplate="%{y:,.0f} M"
            ))

        semanas_ordenadas = sorted(df_semanal["SEMANA"].unique())

        fig.update_xaxes(
            categoryorder='array',
            categoryarray=[str(s) for s in semanas_ordenadas]
        )

        fig.update_layout(
            title="Costo Semanal - Presupuesto Semanal",
            xaxis_title="Semana",
            yaxis_title="Monto",
            barmode="group",
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)


    df_resumen = cargar_resumen_diario()

    cajas_semanales = df_resumen.groupby(
        ["SEMANA","EMPRESA"]
    )["CANTIDAD"].sum().reset_index()

    fig_cajas_sem = go.Figure()

    for empresa in cajas_semanales["EMPRESA"].unique():
        df_emp = cajas_semanales[cajas_semanales["EMPRESA"] == empresa]

        fig_cajas_sem.add_trace(go.Bar(
            x=df_emp["SEMANA"].astype(str),
            y=df_emp["CANTIDAD"],
            name=empresa,
            hovertemplate="%{y:,.0f} "
        ))

    semanas_ordenadas = sorted(cajas_semanales["SEMANA"].unique())

    fig_cajas_sem.update_xaxes(
        categoryorder="array",
        categoryarray=[str(s) for s in semanas_ordenadas]
    )

    fig_cajas_sem.update_layout(
        title="Cajas Pickeadas por Semana",
        xaxis_title="Semana",
        yaxis_title="Cantidad de Cajas",
        barmode="group",
        template="plotly_white"
    )

    st.plotly_chart(fig_cajas_sem, use_container_width=True)


with tab2:
    df_diario = cargar_datos_diario()

    if df_diario.empty:
        st.warning("No se encontraron datos en DASHBOARD DIARIO")
    else:
        turnos = sorted(df_diario["TURNO"].dropna().unique())
        turno_sel = st.multiselect(
            "Filtrar Turno",
            options=turnos,
            default=turnos,
            key="turno_diario"
        )

        df_diario = df_diario[df_diario["TURNO"].isin(turno_sel)]

        df_diario["TIPO"] = df_diario["EMPRESA"].str.contains(
            "picking", case=False, na=False
        ).map({True: "Picking", False: "Trafico/Bodega"})

        total_empresas = df_diario.groupby(
            ["FECHA","EMPRESA"]
        )["PAGO_REAL"].sum().reset_index()

        presupuesto_tipo = df_diario.groupby(
            ["FECHA","TIPO"]
        )["PPTO_DIARIO"].first().reset_index()

        fig = go.Figure()

        for empresa in total_empresas["EMPRESA"].unique():
            df_emp = total_empresas[total_empresas["EMPRESA"] == empresa]

            fig.add_trace(go.Bar(
                x=df_emp["FECHA"].dt.strftime("%d-%m-%Y"),
                y=df_emp["PAGO_REAL"],
                name=empresa,
                hovertemplate="%{y:,.0f}"
            ))

        for tipo in presupuesto_tipo["TIPO"].unique():
            df_pp = presupuesto_tipo[presupuesto_tipo["TIPO"] == tipo]

            fig.add_trace(go.Scatter(
                x=df_pp["FECHA"].dt.strftime("%d-%m-%Y"),
                y=df_pp["PPTO_DIARIO"],
                mode="lines+markers",
                name=f"Presupuesto {tipo}",
                line=dict(width=3),
                hovertemplate="%{y:,.0f}"
            ))

        fechas_ordenadas = sorted(df_diario["FECHA"].unique())

        fig.update_xaxes(
            categoryorder='array',
            categoryarray=[f.strftime("%d-%m-%Y") for f in fechas_ordenadas]
        )

        fig.update_layout(
            title="Costo Diario - Presupuesto DIario",
            xaxis_title="Fecha",
            yaxis_title="Monto",
            barmode="group",
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    df_resumen = cargar_resumen_diario()

    if not df_resumen.empty:

        df_resumen = df_resumen[
            df_resumen["CARGO"].str.upper() == "PICKEADOR"
        ]

        turnos = sorted(df_resumen["TURNO"].dropna().unique())
        turno_sel = st.multiselect(
            "Turno Cajas Pickeadas",
            options=turnos,
            default=turnos,
            key="turno_cajas_diario"
        )

        df_resumen = df_resumen[df_resumen["TURNO"].isin(turno_sel)]

        cajas_diarias = df_resumen.groupby(
            ["FECHA","EMPRESA"]
        )["CANTIDAD"].sum().reset_index()

        fig_cajas_dia = go.Figure()

        for empresa in cajas_diarias["EMPRESA"].unique():
            df_emp = cajas_diarias[cajas_diarias["EMPRESA"] == empresa]

            fig_cajas_dia.add_trace(go.Bar(
                x=df_emp["FECHA"],
                y=df_emp["CANTIDAD"],
                name=empresa,
                hovertemplate="%{y:,.0f} "
            ))

        fig_cajas_dia.update_xaxes(
            tickformat="%d-%m-%Y",
            type="date"
        )


        fig_cajas_dia.update_layout(
            title="Cajas Pickeadas por Día",
            xaxis_title="Fecha",
            yaxis_title="Cantidad de Cajas",
            barmode="group",
            template="plotly_white"
        )

        st.plotly_chart(fig_cajas_dia, use_container_width=True)


