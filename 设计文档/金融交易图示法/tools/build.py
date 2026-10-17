"""Build matching SVG diagrams and printable PDFs from FTN Markdown sources."""

import argparse
import html
import json
from collections import defaultdict
from decimal import Decimal
import math
import re
from pathlib import Path
from string import Template

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from validate import balance_changes, validate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parents[1] / "output" / "pdf"
INK = "#263746"
GREEN = "#d3f2da"
BLUE = "#d8edf4"
GRAY = "#e6e9ec"
YELLOW = "#fff6c4"
WHITE = "#ffffff"


class Scene:
    """A small vector scene, rendered identically to SVG and PDF."""

    def __init__(self, height=330):
        self.width, self.height, self.shapes = 900, height, []

    def text(self, x, y, text, size=18, anchor="middle", fill=INK):
        self.shapes.append(("text", x, y, text, size, anchor, fill))

    def rect(self, x, y, w, h, fill=WHITE, dash=None, radius=0):
        self.shapes.append(("rect", x, y, w, h, fill, dash, radius))

    def circle(self, x, y, text, fill=WHITE, radius=36):
        self.shapes.append(("circle", x, y, radius, fill))
        lines = text.split("\n")
        for i, label in enumerate(lines):
            size = min(
                17, (2 * radius - 12) / max(pdfmetrics.stringWidth(label, "CJK", 1), 1)
            )
            self.text(x, y + 6 + (i - (len(lines) - 1) / 2) * 21, label, size)

    def line(self, points, kind="L", label=None, lx=None, ly=None):
        self.shapes.append(("line", points, kind))
        if label:
            self.text(
                lx or sum(p[0] for p in (points[0], points[-1])) / 2,
                ly or sum(p[1] for p in (points[0], points[-1])) / 2 - 13,
                label,
                17,
            )

    def note(self, x, y, w, lines):
        h = 24 * len(lines) + 20
        self.shapes.append(("note", x, y, w, h))
        for i, line in enumerate(lines):
            self.text(x + 12, y + 27 + i * 24, line, 16, "start")

    def party(self, x, y, w, h, title):
        self.rect(x, y, w, h, "#fafbfc", radius=8)
        self.text(x + 12, y + 25, title, 17, "start")

    def save(self, path):
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{self.height}" viewBox="0 0 900 {self.height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            '<g font-family="Arial Unicode MS, PingFang SC, Noto Sans CJK SC, sans-serif" stroke-linejoin="round" stroke-linecap="round">',
        ]
        for item in self.shapes:
            kind, *v = item
            if kind == "text":
                x, y, txt, size, anchor, fill = v
                parts.append(
                    f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}">{html.escape(txt)}</text>'
                )
            elif kind == "circle":
                x, y, r, fill = v
                parts.append(
                    f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{INK}" stroke-width="1.8"/>')
            elif kind == "rect":
                x, y, w, h, fill, dash, radius = v
                ds = f' stroke-dasharray="{dash}"' if dash else ""
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{INK}" stroke-width="1.5"{ds}/>')
            elif kind == "note":
                x, y, w, h = v
                points = [
                    (x, y),
                    (x + w - 18, y),
                    (x + w, y + 18),
                    (x + w, y + h),
                    (x, y + h),
                ]
                ps = " ".join(f"{a},{b}" for a, b in points)
                parts.append(
                    f'<polygon points="{ps}" fill="{YELLOW}" stroke="{INK}" stroke-width="1.3"/>'
                )
                parts.append(
                    f'<path d="M{x + w - 18},{y} v18 h18" fill="none" stroke="{INK}"/>'
                )
            elif kind == "line":
                points, lk = v
                poly = " ".join(f"{x},{y}" for x, y in points)
                dash = (
                    ' stroke-dasharray="10 7"'
                    if lk == "L"
                    else ' stroke-dasharray="2 5"'
                    if lk in {"N", "I"}
                    else ""
                )
                width = 2.5 if lk == "F" else 1.8
                parts.append(
                    f'<polyline points="{poly}" fill="none" stroke="{INK}" stroke-width="{width}"{dash}/>')
                if lk != "N":
                    tri = arrow(points)
                    ps = " ".join(f"{x},{y}" for x, y in tri)
                    fill = "white" if lk == "I" else INK
                    parts.append(
                        f'<polygon points="{ps}" fill="{fill}" stroke="{INK}" stroke-width="1.5"/>'
                    )
        parts.extend(["</g>", "</svg>"])
        path.write_text("\n".join(parts) + "\n")


def arrow(points):
    (a, b), (x, y) = points[-2:]
    angle = math.atan2(y - b, x - a)
    return [
        (x, y),
        (
            x - 11 * math.cos(angle) + 5 * math.sin(angle),
            y - 11 * math.sin(angle) - 5 * math.cos(angle),
        ),
        (
            x - 11 * math.cos(angle) - 5 * math.sin(angle),
            y - 11 * math.sin(angle) + 5 * math.cos(angle),
        ),
    ]


class Diagram(Flowable):
    def __init__(self, scene, width):
        super().__init__()
        self.scene, self.width = scene, width
        self.height = scene.height * width / scene.width

    def draw(self):
        canvas = self.canv
        scale = self.width / self.scene.width
        canvas.saveState()
        canvas.scale(scale, scale)
        h = self.scene.height
        for kind, *v in self.scene.shapes:
            canvas.setStrokeColor(colors.HexColor(INK))
            canvas.setLineWidth(1.8)
            canvas.setDash()
            if kind == "text":
                x, y, txt, size, anchor, fill = v
                canvas.setFillColor(colors.HexColor(fill))
                canvas.setFont("CJK", size)
                method = (
                    canvas.drawCentredString
                    if anchor == "middle"
                    else canvas.drawRightString
                    if anchor == "end"
                    else canvas.drawString
                )
                method(x, h - y, txt)
            elif kind == "circle":
                x, y, r, fill = v
                canvas.setFillColor(colors.HexColor(fill))
                canvas.circle(x, h - y, r, fill=1)
            elif kind == "rect":
                x, y, w, hh, fill, dash, radius = v
                canvas.setFillColor(colors.HexColor(fill))
                if dash:
                    canvas.setDash([float(n) for n in dash.split()])
                canvas.roundRect(x, h - y - hh, w, hh, radius, fill=1)
            elif kind == "note":
                x, y, w, hh = v
                p = canvas.beginPath()
                for idx, (px, py) in enumerate(
                    [
                        (x, y),
                        (x + w - 18, y),
                        (x + w, y + 18),
                        (x + w, y + hh),
                        (x, y + hh),
                    ]
                ):
                    (p.moveTo if idx == 0 else p.lineTo)(px, h - py)
                p.close()
                canvas.setFillColor(colors.HexColor(YELLOW))
                canvas.drawPath(p, fill=1)
                canvas.lines(
                    [
                        (x + w - 18, h - y, x + w - 18, h - y - 18),
                        (x + w - 18, h - y - 18, x + w, h - y - 18),
                    ]
                )
            elif kind == "line":
                points, lk = v
                if lk == "L":
                    canvas.setDash(10, 7)
                if lk in {"N", "I"}:
                    canvas.setDash(2, 5)
                p = canvas.beginPath()
                for idx, (x, y) in enumerate(points):
                    (p.moveTo if idx == 0 else p.lineTo)(x, h - y)
                canvas.setLineWidth(2.5 if lk == "F" else 1.8)
                canvas.drawPath(p)
                if lk != "N":
                    p = canvas.beginPath()
                    for idx, (x, y) in enumerate(arrow(points)):
                        (p.moveTo if idx == 0 else p.lineTo)(x, h - y)
                    p.close()
                    canvas.setDash()
                    canvas.setFillColor(
                        colors.white if lk == "I" else colors.HexColor(INK)
                    )
                    canvas.setLineWidth(1.5)
                    canvas.drawPath(p, fill=1)
        canvas.restoreState()


def amount(money):
    precision = MODELS[0]["currency_scale"][money["currency"]]
    value = Decimal(money["minor"]) / (10 ** precision)
    return f"{value:,.{precision}f}".removesuffix(".00")


def load_models():
    return [
        json.loads(
            (ROOT /
             "examples" /
             f"{name}.json").read_text()) for name in (
            "payout",
            "refund")]


MODELS = load_models()


def journal_card(scene, model, journal, x, y):
    accounts = {a["id"]: a for a in model["accounts"]}
    events = {e["id"]: e for e in model["events"]}
    height = 45 + len(journal["rows"]) * 27
    scene.rect(x, y, 280, height, "#f7f9fb", radius=6)
    scene.text(x + 140,
               y + 26,
               f'{journal["id"]} / {journal["event_ref"]} {events[journal["event_ref"]]["name"]}',
               16)
    for index, row in enumerate(journal["rows"]):
        name = accounts[row["account_ref"]]["name"].replace("客户余额·", "客户").replace("DBS·", "")
        scene.text(x + 12, y + 53 + index * 27,
                   f'{row["side"]}  {name}  {amount(row["money"])}', 15, "start")
    return height


def business_scene(model, refund=False):
    s = Scene(680)
    s.text(20, 28, model["scenario"]["id"] + "  /  USD  /  分析主体 PSP", 20, "start")
    s.party(15, 55, 365, 525, "P_PSP · 本例账内视角")
    s.party(420, 55, 155, 525, "P_IBC · 图外")
    s.text(195, 104, "银行存款由 DBS 维护", 15)
    positions = {
        "A_AVAIL": (100, 155, GREEN),
        "A_TRANSIT" if refund else "A_FROZEN": (100, 315, GREEN),
        "A_REVENUE": (100, 490, "#f1dcf7"),
        "A_BANK_C": (265, 155, GRAY),
        "A_CHANNEL": (290, 315, BLUE),
        "A_BANK_O": (265, 490, GRAY),
        "X_IBC": (497, 315, BLUE),
    }
    short = {
        "A_AVAIL": "客户可用\n2202-01", "A_FROZEN": "客户冻结\n2202-07",
        "A_TRANSIT": "客户待结算\n2202-04", "A_REVENUE": "服务费收入\n6001-04",
        "A_BANK_C": "客户资金户\n1002-04", "A_CHANNEL": "渠道往来\n2241-20",
        "A_BANK_O": "自有资金户\n1002-32", "X_IBC": "IBC 资金户\nX_IBC",
    }
    for aid, (x, y, fill) in positions.items():
        s.circle(x, y, short[aid], fill, 48)
    flows = {f["id"]: f for f in model["flows"]}

    def draw(fid, points, x, y):
        f = flows[fid]
        s.line(points, f["kind"])
        label = f'{fid} / {f["event_ref"]}'
        size = min(15, 66 / pdfmetrics.stringWidth(label, "CJK", 1))
        s.text(x, y, label, size)
        s.text(x, y + 22, amount(f["money"]), 17)

    if refund:
        draw("F_R1", [(497, 267), (497, 155), (313, 155)], 345, 120)
        draw("F_R2", [(497, 363), (497, 490), (313, 490)], 345, 516)
        draw("L_R1", [(242, 315), (148, 315)], 195, 270)
        draw("L_R2", [(100, 442), (100, 363)], 170, 398)
        draw("L_R3", [(100, 267), (100, 203)], 170, 228)
        s.text(195, 565, "R2：渠道成本自然余额 -10", 16)
        note = ["本例：本金 1,000、客户服务费 15、渠道手续费 10 全退。", "F 是资金划转；L 是账内变化；渠道退费不追加到客户退款。"]
    else:
        draw("L1", [(100, 203), (100, 267)], 170, 228)
        draw("F1", [(313, 155), (497, 155), (497, 267)], 345, 120)
        draw("L2", [(148, 315), (242, 315)], 195, 270)
        draw("L3", [(100, 363), (100, 442)], 170, 398)
        draw("F2", [(313, 490), (497, 490), (497, 363)], 345, 516)
        s.text(195, 565, "E4：渠道成本自然余额 +10", 16)
        note = ["本例：客户扣款 1,015 = 本金 1,000 + 服务费 15。", "渠道成本 10 从自有资金户支付；图中不展开后续收入资金划拨。"]
    y = 55
    for journal in model["journals"]:
        y += journal_card(s, model, journal, 605, y) + 12
    s.note(15, 600, 870, note)
    return s


def diagrams():
    scenes = {}
    s = Scene(255)
    for x, title, lines, fill in [
        (15, "场景卡", ["本金 1,000 / 服务费 15", "渠道成本 10 USD", "规则、假设、分析边界"], YELLOW),
        (315, "业务图", ["账户与资金位置", "F 资金 / L 账内 / I 信息", "统一业务事件编号"], GREEN),
        (615, "关联表格", ["事件与成立条件", "会计分录、示例明细", "逐项核对金额与归属"], BLUE),
    ]:
        s.rect(x, 25, 270, 172, fill, radius=8)
        s.text(x + 135, 59, title, 24)
        for i, line in enumerate(lines):
            s.text(x + 135, 96 + i * 32, line, 18)
    s.text(450, 237, "同一场景、同一事件、同一金额口径；不同视角不重复合计", 19)
    scenes["01-overview"] = s
    s = Scene(335)
    s.party(15, 15, 260, 140, "P 参与方 / 账户维护主体")
    s.circle(145, 100, "A 客户可用\n负债 / USD", GREEN, 44)
    for y, kind, label in [(62, "F", "F 实际资金划转"), (111, "L", "L 账内变化 / 分配"), (160, "I", "I 业务信息")]:
        s.line([(325, y), (565, y)], kind)
        s.text(590, y + 6, label, 19, "start")
    s.note(15, 195, 410, ["已定规则 / 本例假设 / 待决问题", "黄色便笺；说明引线不带箭头。"])
    s.text(660, 236, "F1 / E2 · 1,000 USD", 19)
    s.text(660, 269, "边编号 / 事件编号 · 金额", 17)
    s.text(450, 324, "颜色辅助分类；线型与字母固定；坐标默认不表示先后。", 18)
    scenes["02-legend"] = s
    scenes["03-payout"] = business_scene(MODELS[0])
    scenes["04-refund"] = business_scene(MODELS[1], True)
    s = Scene(480)
    for y, model in [(20, MODELS[0]), (255, MODELS[1])]:
        s.text(20, y + 20, model["scenario"]["id"] + " · 业务信息视图", 19, "start")
        s.rect(25, y + 44, 170, 125, GREEN, radius=7)
        s.text(110, y + 78, "客户", 21)
        s.rect(345, y + 44, 210, 125, GRAY, radius=7)
        s.text(450, y + 78, "PSP", 21)
        s.rect(720, y + 44, 155, 125, BLUE, radius=7)
        s.text(798, y + 78, "IBC", 21)
    s.line([(195, 115), (345, 115)], "I")
    s.text(270, 102, "I1 / E1", 17)
    s.text(270, 148, "付款指令", 17)
    s.line([(720, 115), (555, 115)], "I")
    s.text(637, 102, "I2 / E3", 17)
    s.text(637, 148, "付款完成确认", 17)
    s.line([(720, 175), (555, 175)], "I")
    s.text(637, 200, "I3 / E4 · 渠道扣费通知", 16)
    s.line([(720, 350), (555, 350)], "I")
    s.text(637, 337, "I_R1 / R1", 17)
    s.text(637, 383, "本金退回通知", 17)
    s.line([(345, 350), (195, 350)], "I")
    s.text(270, 337, "I_R2 / R4", 17)
    s.text(270, 383, "退款完成通知", 17)
    s.text(450, 465, "信息视图不增加资金金额；通过事件编号关联同一业务图。", 18)
    scenes["05-information"] = s
    return scenes


def html_table(headers, rows):
    head = "".join(f"<th>{html.escape(str(v))}</th>" for v in headers)
    body = "".join(
        "<tr>" +
        "".join(
            f"<td>{
                html.escape(
                    str(v))}</td>" for v in row) +
        "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_example_html(model, stem, scene_key):
    accounts = {a["id"]: a for a in model["accounts"]}
    parties = {p["id"]: p["name"] for p in model["parties"]}
    journal_ids = defaultdict(list)
    for journal in model["journals"]:
        journal_ids[journal["event_ref"]].append(journal["id"])
    events = html_table(
        ["事件", "成立条件", "前置事件", "分录"],
        [(e["id"] + " " + e["name"], e["condition"], ", ".join(e["after"]) or "无",
          ", ".join(journal_ids[e["id"]])) for e in model["events"]],
    )
    entries = html_table(
        ["分录 / 事件", "方向", "科目", "账户", "金额 USD"],
        [(j["id"] + " / " + j["event_ref"], row["side"],
          accounts[row["account_ref"]]["code"], accounts[row["account_ref"]]["name"],
          amount(row["money"])) for j in model["journals"] for row in j["rows"]],
    )
    records = html_table(
        ["明细", "订单", "视角", "业务含义", "金额 USD", "事件"],
        [(r["id"], r["order_ref"], r["perspective"], r["meaning"], amount(r["money"]),
          ", ".join(r["event_refs"])) for r in model["records"]],
    )
    infos = html_table(
        ["信息 / 事件", "发送方 → 接收方", "业务含义"],
        [(i["id"] + " / " + i["event_ref"],
          parties[i["from_party"]] + " → " + parties[i["to_party"]], i["meaning"])
         for i in model["information"]],
    )
    changes = balance_changes(model)
    deltas = []
    for aid, account in accounts.items():
        if account["kind"] == "external":
            continue
        value = sum(change.get(aid, 0) for change in changes.values())
        sign = "-" if value < 0 else "+" if value > 0 else ""
        label = sign + amount({"currency": account["currency"], "minor": abs(value)})
        deltas.append((account["code"], account["name"], label))
    template = Template((ROOT / "tools" / "example-template.html").read_text())
    page = template.substitute(
        title=html.escape(model["scenario"]["title"]),
        scenario_id=model["scenario"]["id"],
        other_stem="refund" if stem == "payout" else "payout",
        other_name="退款" if stem == "payout" else "出款",
        assumptions="".join(f"<li>{html.escape(v)}</li>" for v in model["scenario"]["assumptions"]),
        scope=html.escape(model["scenario"]["scope"]),
        svg=(ROOT / "figures" / f"{scene_key}.svg").read_text(),
        events=events, entries=entries, records=records, infos=infos,
        deltas=html_table(["科目", "账户", "本次自然余额变化 USD"], deltas),
    )
    (ROOT / "examples" / f"{stem}.html").write_text(page)


def markup(text):
    text = html.escape(text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<link href="\2" color="#25697b">\1</link>',
        text,
    )
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`([^`]+)`", r'<font color="#25697b">\1</font>', text)


def styles():
    base = {
        "fontName": "CJK",
        "fontSize": 10.1,
        "leading": 15.6,
        "wordWrap": "CJK",
        "textColor": colors.HexColor(INK),
        "spaceAfter": 9,
    }
    return {
        "body": ParagraphStyle("body", **base),
        "h1": ParagraphStyle(
            "h1", **dict(base, fontSize=27, leading=35, spaceBefore=14, spaceAfter=16)
        ),
        "h2": ParagraphStyle(
            "h2",
            **dict(
                base,
                fontSize=18,
                leading=26,
                spaceBefore=6,
                spaceAfter=14,
                keepWithNext=True,
            ),
        ),
        "caption": ParagraphStyle(
            "caption",
            **dict(
                base,
                fontSize=8.7,
                leading=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#596b77"),
                spaceAfter=14,
            ),
        ),
        "table": ParagraphStyle(
            "table", **dict(base, fontSize=8.8, leading=13, spaceAfter=0)
        ),
        "th": ParagraphStyle("th", **dict(base, fontSize=9, leading=13, spaceAfter=0)),
        "code": ParagraphStyle(
            "code",
            **dict(
                base,
                fontSize=8.1,
                leading=12,
                backColor=colors.HexColor("#f2f5f7"),
                borderPadding=8,
                spaceAfter=12,
            ),
        ),
    }


def build_pdf(source, target, scenes):
    width = 595.276 - 96
    st = styles()
    doc = SimpleDocTemplate(
        str(target),
        pagesize=(595.276, 841.89),
        rightMargin=48,
        leftMargin=48,
        topMargin=53,
        bottomMargin=48,
        title=source.stem + " | FTN 1.1",
        author="FTN design proposal",
        allowSplitting=True,
    )
    story = []
    lines = source.read_text().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == "<!-- pagebreak -->":
            story.append(PageBreak())
            i += 1
            continue
        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            story.append(Preformatted("\n".join(block), st["code"], maxLineLength=91))
            i += 1
            continue
        figure = re.match(r"!\[(.*?)\]\(figures/(.*?)\.svg\)", line)
        if figure:
            caption, key = figure.groups()
            story.append(Diagram(scenes[key], width))
            story.append(Spacer(1, 6))
            story.append(Paragraph(markup(caption), st["caption"]))
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[:\- ]+", c) for c in raw):
                    rows.append(raw)
                i += 1
            count = len(rows[0])
            weights = {
                2: [0.21, 0.79],
                3: [0.21, 0.39, 0.40],
                4: [0.23, 0.24, 0.28, 0.25],
            }.get(count, [1 / count] * count)
            cells = [
                [Paragraph(markup(c), st["th" if r == 0 else "table"]) for c in row]
                for r, row in enumerate(rows)
            ]
            table = Table(
                cells,
                colWidths=[width * w for w in weights],
                repeatRows=1,
                hAlign="LEFT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f1f3")),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#8da9b2")),
                        (
                            "LINEBELOW",
                            (0, 1),
                            (-1, -1),
                            0.3,
                            colors.HexColor("#d7e0e4"),
                        ),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            story.extend([table, Spacer(1, 12)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(markup(line[2:]), st["h1"]))
            i += 1
            continue
        if line.startswith("## "):
            story.append(Paragraph(markup(line[3:]), st["h2"]))
            i += 1
            continue
        paragraph = [line]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].startswith(("#", "|", "```", "![", "<!--"))
        ):
            if re.match(r"^(\d+\.|-) ", lines[i]):
                break
            paragraph.append(lines[i].strip())
            i += 1
        story.append(Paragraph(markup(" ".join(paragraph)), st["body"]))

    def footer(canvas, document):
        canvas.setFont("CJK", 8)
        canvas.setFillColor(colors.HexColor("#657a86"))
        canvas.drawString(
            48,
            815,
            "FTN 1.1  /  "
            + ("规范" if source.stem == "规范" else "改进说明")
            + "  /  Proposal",
        )
        canvas.setStrokeColor(colors.HexColor("#dbe3e7"))
        canvas.setLineWidth(0.5)
        canvas.line(48, 805, 547, 805)
        canvas.drawString(48, 27, "2026-10-17  ·  Financial Transaction Notation")
        canvas.drawRightString(547, 27, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--font", type=Path, required=True, help="CJK-capable TrueType font file"
    )
    args = parser.parse_args()
    pdfmetrics.registerFont(TTFont("CJK", str(args.font)))
    pdfmetrics.registerFontFamily(
        "CJK", normal="CJK", bold="CJK", italic="CJK", boldItalic="CJK"
    )
    for model in MODELS:
        errors = validate(model)
        if errors:
            raise ValueError("\n".join(errors))
    scenes = diagrams()
    (ROOT / "figures").mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, scene in scenes.items():
        scene.save(ROOT / "figures" / f"{name}.svg")
    for model, stem, scene_key in zip(MODELS, ("payout", "refund"), ("03-payout", "04-refund")):
        build_example_html(model, stem, scene_key)
    for stem in ["规范", "改进说明"]:
        target = OUT / f"金融交易图示法-{stem}-v1.1.pdf"
        build_pdf(ROOT / f"{stem}.md", target, scenes)
        print(target.name)


if __name__ == "__main__":
    main()
