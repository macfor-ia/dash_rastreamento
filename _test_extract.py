def _mpl_fig_to_rlimage(fig, width_cm: float) -> RLImage:
    """Renderiza uma figura matplotlib como PNG e devolve como Image do reportlab."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    px_w, px_h = PILImage.open(buf).size
    buf.seek(0)
    height_cm = width_cm * (px_h / px_w)
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
    return card


def _draw_header_footer(canvas, doc):
    """Cabeçalho/rodapé de marca (logo + linha azul + tagline), repetido em toda página."""
    canvas.saveState()
    page_w, page_h = A4

    # Cabeçalho: "MACFOR" à esquerda, logo à direita, linha azul de separação.
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.HexColor(MACFOR_BLUE))
    canvas.drawString(1.5 * cm, page_h - 1.15 * cm, "MACFOR")

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
    fig, ax = plt.subplots(figsize=(7, 4))
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
    fig, ax = plt.subplots(figsize=(fig_width, 4.6))

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
    title_style = ParagraphStyle(
        "MacforTitle",
        parent=styles["Title"],
        textColor=colors.HexColor(INK_PRIMARY),
        fontName="Helvetica-Bold",
        fontSize=20,
    )
    heading_style = ParagraphStyle(
        "MacforHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor(MACFOR_BLUE),
        fontName="Helvetica-Bold",
    )
    highlight_style = ParagraphStyle(
        "Highlight",
        parent=styles["Normal"],
        fontSize=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor(INK_PRIMARY),
        spaceBefore=10,
        spaceAfter=4,
    )
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8, leading=10)

    elements = []

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    elements.append(Paragraph("Relatório de Uso de Ferramentas — Agente IA", title_style))
    periodo = (
        f"Período analisado: {fdf['created_at'].min():%d/%m/%Y} a {fdf['created_at'].max():%d/%m/%Y}"
        f" &nbsp;|&nbsp; Total de atividades: {len(fdf):,}"
    )
    elements.append(Paragraph(periodo, styles["Normal"]))
    elements.append(Spacer(1, 0.6 * cm))

    # ── 1. Agentes mais utilizados ───────────────────────────────────────────
    elements.append(Paragraph("Agentes Mais Utilizados", heading_style))
    agent_counts = fdf["agent"].value_counts().reset_index()
    agent_counts.columns = ["Agente", "Quantidade"]

    elements.append(_card(_mpl_fig_to_rlimage(_build_agent_pie(agent_counts), width_cm=15)))

    top_agent = agent_counts.iloc[0]
    pct_agent = top_agent["Quantidade"] / agent_counts["Quantidade"].sum() * 100
    elements.append(
        Paragraph(
            f"O agente mais utilizado foi "
            f"<font color='{MACFOR_BLUE}'><b>{top_agent['Agente']}</b></font>, com "
            f"{int(top_agent['Quantidade'])} usos ({pct_agent:.1f}% do total).",
            highlight_style,
        )
    )
    elements.append(PageBreak())

    # ── 2. Usuários ───────────────────────────────────────────────────────────
    elements.append(Paragraph("Usuários", heading_style))

    user_counts = fdf["user_email"].value_counts().reset_index()
    user_counts.columns = ["Usuário", "Quantidade"]

    elements.append(_card(_mpl_fig_to_rlimage(_build_user_bar(user_counts), width_cm=16)))
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
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(MACFOR_BLUE)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(GRID_COLOR)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]
        )
    )
    elements.append(user_table)
    elements.append(PageBreak())

    # ── 3. Uso por ferramenta ────────────────────────────────────────────────
    elements.append(Paragraph("Uso por Ferramenta", heading_style))
    action_counts = fdf["action"].value_counts().reset_index()
    action_counts.columns = ["Ferramenta", "Quantidade"]

    elements.append(_card(_mpl_fig_to_rlimage(_build_tool_bar(action_counts), width_cm=16)))

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


