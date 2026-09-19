import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from dotenv import load_dotenv
from io import BytesIO
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

EXCLUDED_EMAILS = {
    "julia.ledo@macfor.com.br",
    "gustavo.romao@macfor.com.br",
    "resultado@macfor.com.br",
}

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

st.set_page_config(
    page_title="Dashboard de Ferramentas - Agente IA",
    page_icon="🤖",
    layout="wide",
)


@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _fig_to_rlimage(fig, width_cm: float, px_width: int = 1000, px_height: int = 550) -> RLImage:
    """Renderiza uma figura Plotly como PNG (via kaleido) e devolve como Image do reportlab."""
    img_bytes = fig.to_image(format="png", width=px_width, height=px_height, scale=2)
    height_cm = width_cm * (px_height / px_width)
    return RLImage(BytesIO(img_bytes), width=width_cm * cm, height=height_cm * cm)


def build_report_pdf(fdf: pd.DataFrame) -> bytes:
    styles = getSampleStyleSheet()
    highlight_style = ParagraphStyle(
        "Highlight",
        parent=styles["Normal"],
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1a5632"),
        spaceBefore=8,
        spaceAfter=4,
    )
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8, leading=10)

    elements = []

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    elements.append(Paragraph("Relatório de Uso de Ferramentas — Agente IA", styles["Title"]))
    periodo = (
        f"Período analisado: {fdf['created_at'].min():%d/%m/%Y} a {fdf['created_at'].max():%d/%m/%Y}"
        f" &nbsp;|&nbsp; Total de atividades: {len(fdf):,}"
    )
    elements.append(Paragraph(periodo, styles["Normal"]))
    elements.append(Spacer(1, 0.6 * cm))

    # ── 1. Agentes mais utilizados ───────────────────────────────────────────
    elements.append(Paragraph("Agentes Mais Utilizados", styles["Heading2"]))
    agent_counts = fdf["agent"].value_counts().reset_index()
    agent_counts.columns = ["Agente", "Quantidade"]

    fig_agent = px.pie(agent_counts, names="Agente", values="Quantidade", hole=0.4)
    fig_agent.update_traces(textinfo="percent+label")
    elements.append(_fig_to_rlimage(fig_agent, width_cm=14, px_width=900, px_height=600))

    top_agent = agent_counts.iloc[0]
    pct_agent = top_agent["Quantidade"] / agent_counts["Quantidade"].sum() * 100
    elements.append(
        Paragraph(
            f"O agente mais utilizado foi <b>{top_agent['Agente']}</b>, com "
            f"{int(top_agent['Quantidade'])} usos ({pct_agent:.1f}% do total).",
            highlight_style,
        )
    )
    elements.append(PageBreak())

    # ── 2. Usuários ───────────────────────────────────────────────────────────
    elements.append(Paragraph("Usuários", styles["Heading2"]))

    user_counts = fdf["user_email"].value_counts().reset_index()
    user_counts.columns = ["Usuário", "Quantidade"]

    fig_user = px.bar(
        user_counts,
        x="Quantidade",
        y="Usuário",
        orientation="h",
        color="Quantidade",
        color_continuous_scale="Greens",
        text="Quantidade",
    )
    fig_user.update_traces(textposition="outside")
    fig_user.update_layout(
        yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
    )
    user_chart_height = max(500, 40 * len(user_counts))
    elements.append(
        _fig_to_rlimage(fig_user, width_cm=16, px_width=900, px_height=user_chart_height)
    )
    elements.append(Spacer(1, 0.4 * cm))

    user_tools = (
        fdf.groupby("user_email")["action"]
        .apply(lambda s: ", ".join(sorted(s.dropna().unique())))
        .reset_index()
        .rename(columns={"user_email": "Usuário", "action": "Ferramentas Utilizadas"})
    )
    user_summary = user_counts.merge(user_tools, on="Usuário").sort_values(
        "Quantidade", ascending=False
    )

    table_rows = [["Usuário", "Qtd.", "Ferramentas Utilizadas"]]
    for _, row in user_summary.iterrows():
        table_rows.append(
            [
                Paragraph(row["Usuário"], cell_style),
                str(int(row["Quantidade"])),
                Paragraph(row["Ferramentas Utilizadas"], cell_style),
            ]
        )
    user_table = Table(table_rows, colWidths=[5 * cm, 1.5 * cm, 9.5 * cm], repeatRows=1)
    user_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]
        )
    )
    elements.append(user_table)
    elements.append(PageBreak())

    # ── 3. Uso por ferramenta ────────────────────────────────────────────────
    elements.append(Paragraph("Uso por Ferramenta", styles["Heading2"]))
    action_counts = fdf["action"].value_counts().reset_index()
    action_counts.columns = ["Ferramenta", "Quantidade"]

    fig_actions = px.bar(
        action_counts,
        x="Ferramenta",
        y="Quantidade",
        color="Quantidade",
        color_continuous_scale="Blues",
        text="Quantidade",
    )
    fig_actions.update_traces(textposition="outside")
    fig_actions.update_layout(coloraxis_showscale=False, xaxis_tickangle=-35)
    elements.append(_fig_to_rlimage(fig_actions, width_cm=16, px_width=1000, px_height=600))

    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )
    doc.build(elements)
    return output.getvalue()


@st.cache_data(ttl=300)
def load_data():
    client = get_client()
    try:
        page_size = 1000
        all_rows = []
        start = 0
        while True:
            response = (
                client.table("activity_logs")
                .select("*")
                .range(start, start + page_size - 1)
                .execute()
            )
            rows = response.data
            all_rows.extend(rows)
            if len(rows) < page_size:
                break
            start += page_size

        df = pd.DataFrame(all_rows)
        if not df.empty:
            df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", utc=True)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


# ── Header ──────────────────────────────────────────────────────────────────
st.title("🤖 Dashboard de Uso de Ferramentas — Agente IA")

df, error = load_data()

if error:
    st.error(f"Erro ao conectar ao Supabase: `{error}`")
    st.info("Verifique se o arquivo `.env` está correto e se a tabela tem RLS desativado ou uma policy de leitura para a anon key.")
    st.stop()

if df.empty:
    st.warning("Conexão OK, mas a tabela `activity_logs` está vazia ou o RLS está bloqueando a leitura.")
    st.info("No painel do Supabase, vá em **Authentication → Policies** e verifique se há uma policy SELECT para a tabela `activity_logs`.")
    st.stop()

# Lista de agentes completa (antes de excluir perfis) para o filtro da sidebar
all_agents = sorted(df["agent"].dropna().unique().tolist())

# Desconsiderar perfis de teste/serviço da análise
df = df[~df["user_email"].isin(EXCLUDED_EMAILS)]

# ── Sidebar: filtros ─────────────────────────────────────────────────────────
st.sidebar.header("Filtros")

min_date = df["created_at"].dt.date.min()
max_date = df["created_at"].dt.date.max()
date_range = st.sidebar.date_input(
    "Período",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

agents = ["Todos"] + all_agents
selected_agent = st.sidebar.selectbox("Agente", agents)

users = ["Todos"] + sorted(df["user_email"].dropna().unique().tolist())
selected_user = st.sidebar.selectbox("Usuário", users)

if st.sidebar.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

# ── Aplicar filtros ──────────────────────────────────────────────────────────
fdf = df.copy()

if len(date_range) == 2:
    start, end = date_range
    fdf = fdf[
        (fdf["created_at"].dt.date >= start) & (fdf["created_at"].dt.date <= end)
    ]

if selected_agent != "Todos":
    fdf = fdf[fdf["agent"] == selected_agent]

if selected_user != "Todos":
    fdf = fdf[fdf["user_email"] == selected_user]

# ── KPIs ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total de Atividades", f"{len(fdf):,}")
c2.metric("Usuários Únicos", fdf["user_email"].nunique())
c3.metric("Agentes Únicos", fdf["agent"].nunique())
c4.metric("Ferramentas Únicas", fdf["action"].nunique())

st.divider()

# ── 1. Uso por ferramenta ────────────────────────────────────────────────────
st.subheader("Uso por Ferramenta (action)")

action_counts = (
    fdf["action"].value_counts().reset_index()
)
action_counts.columns = ["Ferramenta", "Quantidade"]

fig_actions = px.bar(
    action_counts,
    x="Ferramenta",
    y="Quantidade",
    color="Quantidade",
    color_continuous_scale="Blues",
    text="Quantidade",
)
fig_actions.update_traces(textposition="outside")
fig_actions.update_layout(coloraxis_showscale=False, xaxis_tickangle=-35)
st.plotly_chart(fig_actions, use_container_width=True)

st.divider()

# ── 2. Uso ao longo do tempo ─────────────────────────────────────────────────
st.subheader("Uso ao Longo do Tempo")

granularity = st.radio("Granularidade", ["Dia", "Hora"], horizontal=True)

fdf = fdf.copy()
if granularity == "Dia":
    fdf["period"] = fdf["created_at"].dt.normalize()
else:
    fdf["period"] = fdf["created_at"].dt.floor("h")

time_counts = fdf.groupby("period").size().reset_index(name="Quantidade")

fig_time = px.line(
    time_counts,
    x="period",
    y="Quantidade",
    markers=True,
    labels={"period": "Período"},
)
fig_time.update_traces(line_color="#4C78A8")
st.plotly_chart(fig_time, use_container_width=True)

st.divider()

# ── 3. Uso por agente  +  4. Ranking de usuários ─────────────────────────────
col_agent, col_user = st.columns(2)

with col_agent:
    st.subheader("Uso por Agente")
    agent_counts = fdf["agent"].value_counts().reset_index()
    agent_counts.columns = ["Agente", "Quantidade"]
    fig_agent = px.pie(
        agent_counts,
        names="Agente",
        values="Quantidade",
        hole=0.4,
    )
    fig_agent.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_agent, use_container_width=True)

with col_user:
    st.subheader("Ranking de Usuários Mais Ativos")
    user_counts = fdf["user_email"].value_counts().reset_index()
    user_counts.columns = ["Usuário", "Quantidade"]
    fig_user = px.bar(
        user_counts.head(10),
        x="Quantidade",
        y="Usuário",
        orientation="h",
        color="Quantidade",
        color_continuous_scale="Greens",
        text="Quantidade",
    )
    fig_user.update_traces(textposition="outside")
    fig_user.update_layout(
        yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_user, use_container_width=True)

st.divider()

# ── Relatório ────────────────────────────────────────────────────────────────
st.subheader("Relatório")

if st.button("📊 Gerar Relatório"):
    with st.spinner("Gerando PDF..."):
        st.session_state["report_bytes"] = build_report_pdf(fdf)

if "report_bytes" in st.session_state:
    st.download_button(
        label="⬇️ Baixar Relatório (PDF)",
        data=st.session_state["report_bytes"],
        file_name="relatorio_uso_ferramentas.pdf",
        mime="application/pdf",
    )

st.divider()

# ── Tabela de dados brutos ───────────────────────────────────────────────────
with st.expander("Ver dados brutos"):
    st.dataframe(
        fdf[["created_at", "user_email", "agent", "action"]]
        .sort_values("created_at", ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
    )
