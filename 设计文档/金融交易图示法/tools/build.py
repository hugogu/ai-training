"""Build matching SVG diagrams and printable PDFs from FTN Markdown sources."""

import argparse
import html
import math
import re
from pathlib import Path

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
                    f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{INK}" stroke-width="1.8"/>'
                )
            elif kind == "rect":
                x, y, w, h, fill, dash, radius = v
                ds = f' stroke-dasharray="{dash}"' if dash else ""
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{INK}" stroke-width="1.5"{ds}/>'
                )
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
                    if lk == "M"
                    else ' stroke-dasharray="2 5"'
                    if lk in {"N", "T"}
                    else ""
                )
                width = 5 if lk == "F" else 1.8
                parts.append(
                    f'<polyline points="{poly}" fill="none" stroke="{INK}" stroke-width="{width}"{dash}/>'
                )
                if lk == "F":
                    parts.append(
                        f'<polyline points="{poly}" fill="none" stroke="white" stroke-width="2.1"/>'
                    )
                if lk != "N":
                    tri = arrow(points)
                    ps = " ".join(f"{x},{y}" for x, y in tri)
                    fill = "white" if lk == "M" else INK
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
                if lk == "M":
                    canvas.setDash(10, 7)
                if lk in {"N", "T"}:
                    canvas.setDash(2, 5)
                p = canvas.beginPath()
                for idx, (x, y) in enumerate(points):
                    (p.moveTo if idx == 0 else p.lineTo)(x, h - y)
                canvas.setLineWidth(5 if lk == "F" else 1.8)
                canvas.drawPath(p)
                if lk == "F":
                    canvas.setStrokeColor(colors.white)
                    canvas.setLineWidth(2.1)
                    canvas.drawPath(p)
                    canvas.setStrokeColor(colors.HexColor(INK))
                if lk != "N":
                    p = canvas.beginPath()
                    for idx, (x, y) in enumerate(arrow(points)):
                        (p.moveTo if idx == 0 else p.lineTo)(x, h - y)
                    p.close()
                    canvas.setDash()
                    canvas.setFillColor(
                        colors.white if lk == "M" else colors.HexColor(INK)
                    )
                    canvas.setLineWidth(1.5)
                    canvas.drawPath(p, fill=1)
        canvas.restoreState()


def diagrams():
    scenes = {}
    s = Scene(310)
    for y, title, left, right, kind, label in [
        (20, "消息层", "P 服务商", "P 银行", "M", "M1 付款请求"),
        (115, "本地账务层", "A 客户钱包", "A 付款中间户", "L", "L1 100 USD | posted"),
        (
            210,
            "外部资金层",
            "A 服务商银行户",
            "A 受益人银行户",
            "F",
            "F1 100 USD | confirmed",
        ),
    ]:
        s.text(26, y + 40, title, 19, "start")
        if kind == "M":
            s.rect(200, y + 8, 185, 54)
            s.text(292, y + 43, left, 19)
            s.rect(660, y + 8, 210, 54)
            s.text(765, y + 43, right, 19)
            start, end = 385, 660
        else:
            s.circle(290, y + 35, left, GREEN if kind == "L" else BLUE, 53)
            s.circle(760, y + 35, right, GRAY if kind == "L" else BLUE, 58)
            start, end = 350, 695
        s.line([(start, y + 35), (end, y + 35)], kind, label, 520, y + 19)
    s.text(525, 302, "同一本金：F1 realizes L1；不可重复计入客户付款", 17)
    scenes["01-overview"] = s
    s = Scene(350)
    s.party(15, 15, 210, 140, "P1 机构 / 账户维护方")
    s.circle(120, 100, "A1 | USD", GREEN, 39)
    s.rect(265, 20, 280, 125, WHITE, "7 4 1 4")
    s.text(405, 49, "B1 / ledger=K1", 18)
    s.text(405, 82, "atomic=true", 18)
    s.text(405, 118, "本地提交边界", 17)
    s.rect(585, 20, 295, 125, WHITE, radius=12)
    s.text(732, 52, "G1 / operation=O1", 18)
    s.text(732, 88, "业务归组", 19)
    s.text(732, 120, "不承诺跨机构原子性", 16)
    for y, k, label in [
        (200, "L", "L 单实线：本地账务"),
        (252, "F", "F 双线：外部资金"),
        (304, "M", "M 虚线空心：消息"),
    ]:
        s.line([(35, y), (275, y)], k)
        s.text(310, y + 6, label, 19, "start")
    s.note(620, 185, 255, ["N 黄色注释", "细点线，无箭头", "状态始终使用文字标签"])
    s.line([(610, 235), (560, 260)], "N")
    scenes["02-legend"] = s
    s = Scene(285)
    s.party(15, 15, 420, 220, "P_PROVIDER 服务商 / custodian")
    s.circle(120, 105, "A_WALLET", GREEN, 48)
    s.circle(325, 105, "A_TRANSIT", GRAY, 48)
    s.text(120, 180, "owner=P_CUSTOMER", 17)
    s.text(325, 180, "owner=P_PROVIDER", 17)
    s.text(225, 218, "ledger=K1 / normalized / USD", 17)
    s.party(470, 15, 415, 220, "P_BANK 银行 / custodian")
    s.circle(675, 105, "A_BANK", BLUE, 48)
    s.text(675, 180, "owner=P_PROVIDER", 17)
    s.text(675, 218, "ledger=K_BANK / settlement / USD", 17)
    s.text(450, 270, "摆放按 custodian；owner 另写；同一机构可以维护多类账户", 18)
    scenes["03-ownership"] = s
    s = Scene(325)
    s.rect(15, 15, 425, 240, WHITE, "7 4 1 4")
    s.text(225, 45, "B_SPLIT / K1 / atomic=true", 18)
    s.circle(80, 140, "A1", GREEN)
    s.circle(365, 100, "A2", GRAY)
    s.circle(365, 205, "A3", GRAY)
    s.line(
        [(118, 140), (220, 140), (220, 100), (327, 100)], "L", "L1 | 100 USD", 230, 82
    )
    s.line([(220, 140), (220, 205), (327, 205)], "L", "L2 | 1 USD", 245, 234)
    s.text(80, 205, "Δ=-101", 17)
    s.rect(460, 15, 425, 240, WHITE, "7 4 1 4")
    s.text(672, 45, "B_GATHER / K1 / atomic=true", 18)
    s.circle(525, 100, "A4", GREEN)
    s.circle(525, 205, "A5", GREEN)
    s.circle(820, 150, "A6", GRAY)
    s.line(
        [(563, 100), (675, 100), (675, 150), (782, 150)], "L", "L3 | 60 USD", 680, 82
    )
    s.line([(563, 205), (675, 205), (675, 150)], "L", "L4 | 40 USD", 680, 235)
    s.text(820, 220, "Δ=+100", 17)
    s.note(150, 270, 600, ["同一 commit_ref 才表示本地一次提交；客户活动条数另定"])
    scenes["04-composition"] = s
    s = Scene(330)
    s.line([(30, 90), (870, 90)], "T")
    s.text(860, 120, "t / not to scale", 16, "end")
    for x, label in [
        (95, "e1 请求"),
        (300, "e2 超时"),
        (510, "e3 查询"),
        (740, "e4 明确未执行"),
    ]:
        s.line([(x, 80), (x, 100)], "N")
        s.text(x, 65, label, 18)
    s.note(185, 175, 250, ["F1.state=?", "knowledge=unknown", "保留最后已知 submitted"])
    s.note(
        510,
        175,
        345,
        [
            "只有 e4 证据满足重试门槛",
            "才可建立 F2 retry_of F1",
            "同 O / 同 effect；不再次扣款",
        ],
    )
    s.line([(300, 105), (300, 170)], "N")
    s.line([(740, 105), (740, 170)], "N")
    scenes["05-retry"] = s
    s = Scene(345)
    s.text(450, 25, "FX Q1：1 USD = 2 AUD；不同币种分别闭合", 21)
    s.circle(95, 110, "客户 USD", GREEN, 51)
    s.circle(755, 110, "FX USD", GRAY, 51)
    s.line([(148, 110), (702, 110)], "L", "L_USD | 100 USD", 425, 92)
    s.circle(95, 240, "FX AUD", GRAY, 51)
    s.circle(755, 240, "中间 AUD", GRAY, 51)
    s.line([(148, 240), (702, 240)], "L", "L_AUD | 200 AUD", 425, 222)
    s.note(
        275,
        270,
        500,
        [
            "退回 180 AUD -> 新兑换 85 USD；承诺退款 90 USD",
            "差额 5 USD 单独标为补足义务，不自动等于总 FX P&L",
        ],
    )
    scenes["06-fx"] = s
    s = Scene(450)
    s.rect(15, 15, 870, 415, WHITE, radius=12)
    s.text(450, 43, "G O1：L1、L2 posted 且 F1 confirmed 才完成", 19)
    s.rect(35, 65, 830, 215, WHITE, "7 4 1 4")
    s.text(450, 88, "B1 / K1 / split / atomic=true / commit:B1", 17)
    s.circle(115, 165, "A1\n钱包 USD", GREEN, 48)
    s.circle(725, 145, "A2\n中间 USD", GRAY, 40)
    s.circle(725, 235, "A3\n收入 USD", WHITE, 36)
    s.line(
        [(165, 165), (350, 165), (350, 145), (683, 145)],
        "L",
        "L1 100 USD | posted",
        455,
        130,
    )
    s.line([(350, 165), (350, 235), (687, 235)], "L", "L2 1 USD | posted", 475, 259)
    s.circle(115, 355, "A4\n银行 USD", BLUE, 47)
    s.circle(725, 355, "A5\n银行 USD", BLUE, 47)
    s.line([(164, 355), (675, 355)], "F", "F1 100 USD | confirmed", 445, 335)
    s.text(445, 397, "basis=beneficiary_credit；F1 realizes L1", 17)
    scenes["07-payout"] = s
    s = Scene(465)
    s.text(450, 28, "O_REFUND：退回、补足和客户入账分别确认", 21)
    s.circle(100, 100, "原对端\nAUD 银行户", BLUE, 48)
    s.circle(770, 100, "服务商\nAUD 银行户", BLUE, 52)
    s.line([(150, 100), (715, 100)], "F", "F_RETURN | 180 AUD | confirmed", 430, 80)
    s.note(
        220,
        135,
        495,
        [
            "returns F_PAY（原 200 AUD）；20 AUD 费用不退",
            "新兑换回收 85 USD；原汇率退款承诺 90 USD",
        ],
    )
    s.rect(20, 225, 860, 215, WHITE, "7 4 1 4")
    s.text(45, 250, "B_REF / K_USD", 16, "start")
    s.text(45, 274, "atomic=true / posted / commit:B_REF", 16, "start")
    s.circle(450, 280, "A_TOPUP\n补足账户", WHITE, 34)
    s.circle(100, 380, "A_RCV\n回收资金", GRAY, 46)
    s.circle(450, 380, "A_POOL\n退款池", GRAY, 46)
    s.circle(795, 380, "A_WALLET\n客户钱包", GREEN, 46)
    s.line([(148, 380), (402, 380)], "L", "L_RCV | 85 USD", 275, 360)
    s.line([(498, 380), (747, 380)], "L", "L_REF | 90 USD", 625, 360)
    s.line([(450, 316), (450, 332)], "L")
    s.text(570, 328, "L_TOPUP | 5 USD", 16)
    scenes["08-refund"] = s
    s = Scene(475)
    s.rect(20, 15, 210, 52)
    s.text(125, 48, "P_CUSTOMER", 19)
    s.rect(640, 15, 240, 52)
    s.text(760, 48, "P_PLATFORM", 19)
    s.line([(230, 41), (640, 41)], "M", "M_BOOK / Book Order / 102 USD", 435, 26)
    s.line([(640, 100), (230, 100)], "M", "M_QUOTE / Quote / 100 + 2 USD", 435, 125)
    s.rect(20, 155, 860, 300, WHITE, "7 4 1 4")
    s.text(450, 175, "B_ADD / K1 / split / atomic=true", 18)
    s.text(450, 195, "全部 L posted / commit:B_ADD", 16)
    s.circle(110, 320, "A1\n客户钱包", GREEN, 47)
    for y, aid, name, amount, lid in [
        (230, "A2", "付款中间户", "100", "L1"),
        (320, "A3", "平台收入", "1", "L3"),
        (410, "A4", "SaaS 收入", "1", "L2"),
    ]:
        s.circle(780, y, aid + "\n" + name, GRAY, 38)
        s.line(
            [(158, 320), (350, 320), (350, y), (740, y)],
            "L",
            f"{lid} | {amount} USD",
            540,
            y - 12,
        )
    s.text(110, 400, "Δ=-102 USD", 17)
    scenes["09-addon"] = s
    return scenes


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
        title=source.stem + " | FTN 1.0",
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
                4: [0.39, 0.21, 0.22, 0.18],
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
            "FTN 1.0  /  "
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
    scenes = diagrams()
    (ROOT / "figures").mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, scene in scenes.items():
        scene.save(ROOT / "figures" / f"{name}.svg")
    for stem in ["规范", "改进说明"]:
        target = OUT / f"金融交易图示法-{stem}-v1.0.pdf"
        build_pdf(ROOT / f"{stem}.md", target, scenes)
        print(target.name)


if __name__ == "__main__":
    main()
