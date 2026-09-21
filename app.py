import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from dotenv import load_dotenv
from io import BytesIO
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Identidade visual Macfor (extraída do template oficial de apresentação).
MACFOR_BLUE = "#0a7cf5"
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "macfor_logo.png")

# Paleta validada (skill dataviz / references/palette.md) — modo claro, impressão.
CATEGORICAL_COLORS = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "text.color": INK_PRIMARY,
    "axes.edgecolor": AXIS_COLOR,
    "axes.labelcolor": INK_SECONDARY,
    "xtick.color": INK_SECONDARY,
    "ytick.color": INK_SECONDARY,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})

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


CONTENT_W_CM = 18.0  # largura útil entre as margens (A4 - 1.5cm de cada lado)


def _mpl_fig_to_rlimage(fig, width_cm: float, max_height_cm: float = None) -> RLImage:
    """Renderiza uma figura matplotlib como PNG e devolve como Image do reportlab.

    Se ``max_height_cm`` for informado e a altura resultante ultrapassar o limite
    (ex.: gráfico horizontal com muitas barras), a imagem é reduzida
    proporcionalmente para nunca estourar a página.
    """
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    px_w, px_h = PILImage.open(buf).size
    buf.seek(0)
    height_cm = width_cm * (px_h / px_w)
    if max_height_cm and height_cm > max_height_cm:
        width_cm *= max_height_cm / height_cm
        height_cm = max_height_cm
    return RLImage(buf, width=width_cm * cm, height=height_cm * cm)


def _card(img: RLImage, pad_cm: float = 0.4) -> Table:
    """Envolve uma imagem em um card branco de cantos arredondados, no estilo do template Macfor."""
    pad = pad_cm * cm
    card = Table([[img]], colWidths=[img.drawWidth + 2 * pad])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(AXIS_COLOR)),
                ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                ("LEFTPADDING", (0, 0), (-1, -1), pad),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    card.hAlign = "CENTER"
    return card


def _stat_tile(value: str, label: str, width_cm: float) -> Table:
    """Card de KPI: número em destaque + rótulo, com barra de acento azul no topo."""
    value_style = ParagraphStyle(
        "KpiValue",
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=24,
        textColor=colors.HexColor(INK_PRIMARY),
        alignment=TA_CENTER,
    )
    label_style = ParagraphStyle(
        "KpiLabel",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor(INK_SECONDARY),
        alignment=TA_CENTER,
    )
    tile = Table(
        [[Paragraph(value, value_style)], [Paragraph(label, label_style)]],
        colWidths=[width_cm * cm],
    )
    tile.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(AXIS_COLOR)),
                ("LINEABOVE", (0, 0), (-1, 0), 2.5, colors.HexColor(MACFOR_BLUE)),
                ("TOPPADDING", (0, 0), (-1, 0), 0.5 * cm),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0.05 * cm),
                ("TOPPADDING", (0, 1), (-1, 1), 0.05 * cm),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 0.45 * cm),
                ("LEFTPADDING", (0, 0), (-1, -1), 0.2 * cm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0.2 * cm),
            ]
        )
    )
    return tile


def _kpi_row(items, total_width_cm: float = CONTENT_W_CM, gap_cm: float = 0.45) -> Table:
    """Uma linha de tiles de KPI, distribuídos ao longo de ``total_width_cm``."""
    n = len(items)
    tile_w = (total_width_cm - gap_cm * (n - 1)) / n
    row_cells, col_widths = [], []
    for i, (value, label) in enumerate(items):
        if i:
            row_cells.append("")
            col_widths.append(gap_cm * cm)
        row_cells.append(_stat_tile(value, label, tile_w))
        col_widths.append(tile_w * cm)
    row = Table([row_cells], colWidths=col_widths)
    row.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return row


def _section_heading(number: str, title: str, width_cm: float = CONTENT_W_CM) -> list:
    """Título de seção no estilo do deck Macfor: número em azul + título + regra fina."""
    style = ParagraphStyle(
        "SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=colors.HexColor(INK_PRIMARY),
    )
    text = f"<font color='{MACFOR_BLUE}'>{number}</font>&nbsp;&nbsp;{title}"
    return [
        Paragraph(text, style),
        Spacer(1, 0.18 * cm),
        HRFlowable(
            width=width_cm * cm,
            thickness=1,
            color=colors.HexColor(AXIS_COLOR),
            spaceAfter=0.4 * cm,
        ),
    ]


def _callout(html_text: str, width_cm: float = CONTENT_W_CM) -> Table:
    """Caixa de destaque (insight) com fundo azul claro e barra de acento à esquerda."""
    style = ParagraphStyle(
        "Callout",
        fontName="Helvetica",
        fontSize=10.5,
        leading=14.5,
        textColor=colors.HexColor(INK_PRIMARY),
    )
    box = Table([[Paragraph(html_text, style)]], colWidths=[width_cm * cm])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(SEQ_BLUE[0])),
                ("LINEBEFORE", (0, 0), (0, 0), 3, colors.HexColor(MACFOR_BLUE)),
                ("TOPPADDING", (0, 0), (-1, -1), 0.3 * cm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3 * cm),
                ("LEFTPADDING", (0, 0), (-1, -1), 0.5 * cm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0.4 * cm),
            ]
        )
    )
    return box


def _ranking_table(rows_data, header, col_widths, header_bg: str = MACFOR_BLUE) -> Table:
    """Tabela de ranking compacta (usada nas seções de agentes e ferramentas)."""
    table = Table([header] + rows_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("TOPPADDING", (0, 0), (-1, -1), 0.18 * cm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.18 * cm),
            ]
        )
    )
    return table


def _draw_header_footer(canvas, doc):
    """Cabeçalho/rodapé de marca (logo + linha azul + tagline), repetido em toda página."""
    canvas.saveState()
    page_w, page_h = A4

    # Cabeçalho: logo à direita, linha azul de separação.
    if os.path.exists(LOGO_PATH):
        logo_w, logo_h = 2.6 * cm, 2.6 * cm / (1120 / 360)
        canvas.drawImage(
            LOGO_PATH,
            page_w - 1.5 * cm - logo_w,
            page_h - 1.0 * cm - logo_h,
            width=logo_w,
            height=logo_h,
        )

    canvas.setStrokeColor(colors.HexColor(MACFOR_BLUE))
    canvas.setLineWidth(1)
    canvas.line(1.5 * cm, page_h - 1.4 * cm, page_w - 1.5 * cm, page_h - 1.4 * cm)

    # Rodapé: tagline à esquerda, número de página à direita.
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor(INK_SECONDARY))
    canvas.drawString(1.5 * cm, 1.1 * cm, "macfor.com.br")
    canvas.drawRightString(page_w - 1.5 * cm, 1.1 * cm, f"{doc.page}")

    canvas.restoreState()


def _seq_blue_colors(values) -> list:
    """Mapeia valores para a rampa sequencial azul (magnitude), evitando a ponta mais clara."""
    vmin, vmax = min(values), max(values)
    cmap = LinearSegmentedColormap.from_list("seq_blue", SEQ_BLUE)
    if vmax == vmin:
        return [cmap(0.75) for _ in values]
    return [cmap(0.3 + 0.7 * (v - vmin) / (vmax - vmin)) for v in values]


def _build_agent_pie(agent_counts: pd.DataFrame):
    n = len(agent_counts)
    total = agent_counts["Quantidade"].sum()
    fig, ax = plt.subplots(figsize=(7, 4.7))
    wedges, _ = ax.pie(
        agent_counts["Quantidade"],
        colors=CATEGORICAL_COLORS[:n],
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 2},
    )
    labels = [
        f"{nome}  —  {qtd} ({qtd / total * 100:.1f}%)"
        for nome, qtd in zip(agent_counts["Agente"], agent_counts["Quantidade"])
    ]
    ax.legend(
        wedges,
        labels,
        loc="center left",
        bbox_to_anchor=(1.05, 0.5),
        frameon=False,
        fontsize=10,
        labelcolor=INK_SECONDARY,
        handlelength=1.2,
    )
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig


def _build_user_bar(user_counts: pd.DataFrame):
    df_sorted = user_counts.sort_values("Quantidade", ascending=True)
    n = len(df_sorted)
    fig_height = max(2.5, 0.42 * n + 0.8)
    fig, ax = plt.subplots(figsize=(9, fig_height))

    vals = df_sorted["Quantidade"].tolist()
    bars = ax.barh(df_sorted["Usuário"], vals, color=_seq_blue_colors(vals), height=0.62)

    max_val = max(vals)
    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_width() + max_val * 0.015,
            bar.get_y() + bar.get_height() / 2,
            str(int(v)),
            va="center",
            fontsize=9,
            color=INK_SECONDARY,
        )

    ax.set_xlim(0, max_val * 1.12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(AXIS_COLOR)
    ax.tick_params(left=False, labelsize=9)
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xticks([])
    fig.tight_layout()
    return fig


def _build_tool_bar(action_counts: pd.DataFrame):
    df_sorted = action_counts.sort_values("Quantidade", ascending=False)
    n = len(df_sorted)
    fig_width = max(7, 0.9 * n + 1.5)
    fig, ax = plt.subplots(figsize=(fig_width, 5.6))

    vals = df_sorted["Quantidade"].tolist()
    x_pos = range(n)
    bars = ax.bar(x_pos, vals, color=_seq_blue_colors(vals), width=0.6)

    max_val = max(vals)
    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_val * 0.02,
            str(int(v)),
            ha="center",
            fontsize=9,
            color=INK_SECONDARY,
        )

    ax.set_ylim(0, max_val * 1.15)
    ax.set_xticks(list(x_pos))
    ax.set_xticklabels(df_sorted["Ferramenta"], rotation=35, ha="right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(AXIS_COLOR)
    ax.tick_params(left=False, bottom=False)
    ax.set_yticks([])
    ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return fig


def build_report_pdf(fdf: pd.DataFrame) -> bytes:
    styles = getSampleStyleSheet()
    CW = CONTENT_W_CM

    title_style = ParagraphStyle(
        "MacforTitle",
        parent=styles["Title"],
        textColor=colors.HexColor(INK_PRIMARY),
        fontName="Helvetica-Bold",
        fontSize=21,
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor(INK_SECONDARY),
    )
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8.5, leading=10.5)
    rank_cell_style = ParagraphStyle("RankCell", parent=styles["Normal"], fontSize=9, leading=11)

    elements = []

    # ── Cabeçalho + KPIs (abertura do relatório) ────────────────────────────
    elements.append(Paragraph("Relatório de Uso de Ferramentas — Agente IA", title_style))
    periodo = (
        f"Período analisado: {fdf['created_at'].min():%d/%m/%Y} a "
        f"{fdf['created_at'].max():%d/%m/%Y}"
    )
    elements.append(Paragraph(periodo, meta_style))
    elements.append(Spacer(1, 0.5 * cm))

    kpis = [
        (f"{len(fdf):,}".replace(",", "."), "Total de atividades"),
        (str(fdf["user_email"].nunique()), "Usuários únicos"),
        (str(fdf["agent"].nunique()), "Agentes únicos"),
        (str(fdf["action"].nunique()), "Ferramentas únicas"),
    ]
    elements.append(_kpi_row(kpis, total_width_cm=CW))
    elements.append(Spacer(1, 0.7 * cm))

    # ── 01. Agentes mais utilizados ──────────────────────────────────────────
    agent_counts = fdf["agent"].value_counts().reset_index()
    agent_counts.columns = ["Agente", "Quantidade"]
    total_agent = int(agent_counts["Quantidade"].sum())
    top_agent = agent_counts.iloc[0]
    pct_agent = top_agent["Quantidade"] / total_agent * 100

    intro_block = _section_heading("01", "Agentes Mais Utilizados", CW) + [
        _callout(
            f"O agente mais utilizado foi "
            f"<font color='{MACFOR_BLUE}'><b>{top_agent['Agente']}</b></font>, com "
            f"{int(top_agent['Quantidade'])} usos ({pct_agent:.1f}% do total).",
            width_cm=CW,
        )
    ]
    elements.append(KeepTogether(intro_block))
    elements.append(Spacer(1, 0.45 * cm))
    elements.append(_card(_mpl_fig_to_rlimage(_build_agent_pie(agent_counts), width_cm=17.3)))
    elements.append(Spacer(1, 0.5 * cm))

    agent_rank_rows = []
    for _, row in agent_counts.iterrows():
        pct = row["Quantidade"] / total_agent * 100
        agent_rank_rows.append(
            [
                Paragraph(str(row["Agente"]), rank_cell_style),
                str(int(row["Quantidade"])),
                f"{pct:.1f}%",
            ]
        )
    elements.append(
        _ranking_table(
            agent_rank_rows,
            header=["Agente", "Usos", "% do Total"],
            col_widths=[11 * cm, 3.5 * cm, 3.5 * cm],
        )
    )
    elements.append(PageBreak())

    # ── 02. Usuários ──────────────────────────────────────────────────────────
    user_counts = fdf["user_email"].value_counts().reset_index()
    user_counts.columns = ["Usuário", "Quantidade"]
    total_user = int(user_counts["Quantidade"].sum())
    top_user = user_counts.iloc[0]
    pct_user = top_user["Quantidade"] / total_user * 100

    intro_block = _section_heading("02", "Usuários", CW) + [
        _callout(
            f"<font color='{MACFOR_BLUE}'><b>{top_user['Usuário']}</b></font> concentra "
            f"{pct_user:.1f}% de todo o uso registrado no período "
            f"({int(top_user['Quantidade'])} de {total_user} atividades).",
            width_cm=CW,
        )
    ]
    elements.append(KeepTogether(intro_block))
    elements.append(Spacer(1, 0.45 * cm))

    user_bar_img = _mpl_fig_to_rlimage(
        _build_user_bar(user_counts), width_cm=17.5, max_height_cm=19
    )
    elements.append(_card(user_bar_img))
    elements.append(Spacer(1, 0.5 * cm))

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
    user_table = Table(table_rows, colWidths=[5.5 * cm, 1.8 * cm, 10.7 * cm], repeatRows=1)
    user_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(MACFOR_BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("TOPPADDING", (0, 0), (-1, -1), 0.15 * cm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.15 * cm),
            ]
        )
    )
    elements.append(user_table)
    elements.append(PageBreak())

    # ── 03. Uso por ferramenta ───────────────────────────────────────────────
    action_counts = fdf["action"].value_counts().reset_index()
    action_counts.columns = ["Ferramenta", "Quantidade"]
    total_action = int(action_counts["Quantidade"].sum())
    top_action = action_counts.iloc[0]
    pct_action = top_action["Quantidade"] / total_action * 100

    intro_block = _section_heading("03", "Uso por Ferramenta", CW) + [
        _callout(
            f"A ferramenta mais utilizada foi "
            f"<font color='{MACFOR_BLUE}'><b>{top_action['Ferramenta']}</b></font>, com "
            f"{int(top_action['Quantidade'])} usos ({pct_action:.1f}% do total).",
            width_cm=CW,
        )
    ]
    elements.append(KeepTogether(intro_block))
    elements.append(Spacer(1, 0.45 * cm))

    tool_img = _mpl_fig_to_rlimage(_build_tool_bar(action_counts), width_cm=17.5, max_height_cm=16)
    elements.append(_card(tool_img))
    elements.append(Spacer(1, 0.5 * cm))

    action_users = fdf.groupby("action")["user_email"].nunique().reset_index()
    action_users.columns = ["Ferramenta", "Usuários"]
    action_summary = action_counts.merge(action_users, on="Ferramenta").sort_values(
        "Quantidade", ascending=False
    )

    tool_rank_rows = []
    for _, row in action_summary.iterrows():
        pct = row["Quantidade"] / total_action * 100
        tool_rank_rows.append(
            [
                Paragraph(str(row["Ferramenta"]), rank_cell_style),
                str(int(row["Quantidade"])),
                f"{pct:.1f}%",
                str(int(row["Usuários"])),
            ]
        )
    elements.append(
        _ranking_table(
            tool_rank_rows,
            header=["Ferramenta", "Usos", "% do Total", "Usuários"],
            col_widths=[8.5 * cm, 3 * cm, 3 * cm, 3.5 * cm],
        )
    )

    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        topMargin=2.1 * cm,
        bottomMargin=1.8 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )
    doc.build(elements, onFirstPage=_draw_header_footer, onLaterPages=_draw_header_footer)
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
