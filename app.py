import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from dotenv import load_dotenv
from io import BytesIO
import os

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


def build_report(fdf: pd.DataFrame) -> bytes:
    # Planilha 1: quantidade de uso por ferramenta para cada usuário
    pivot = pd.crosstab(fdf["user_email"], fdf["action"])
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.reset_index().rename(columns={"user_email": "Usuário"})

    # Planilha 2: quais ferramentas cada usuário usa e quais não usa
    all_tools = sorted(fdf["action"].dropna().unique().tolist())
    rows = []
    for user, group in fdf.groupby("user_email"):
        used = sorted(group["action"].dropna().unique().tolist())
        not_used = [t for t in all_tools if t not in used]
        rows.append({
            "Usuário": user,
            "Ferramentas Utilizadas": ", ".join(used),
            "Ferramentas Não Utilizadas": ", ".join(not_used),
        })
    tools_df = pd.DataFrame(rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pivot.to_excel(writer, sheet_name="Uso por Usuário", index=False)
        tools_df.to_excel(writer, sheet_name="Ferramentas por Usuário", index=False)
    return output.getvalue()


@st.cache_data(ttl=300)
def load_data():
    client = get_client()
    try:
        response = client.table("activity_logs").select("*").execute()
        df = pd.DataFrame(response.data)
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
    st.session_state["report_bytes"] = build_report(fdf)

if "report_bytes" in st.session_state:
    st.download_button(
        label="⬇️ Baixar Relatório (Excel)",
        data=st.session_state["report_bytes"],
        file_name="relatorio_uso_ferramentas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
