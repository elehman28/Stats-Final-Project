"""
Build the Problem Set 4 PDF: handwritten photos + NDCP data questions (Q1-Q4).

Usage:
    cd PS4 && ../.venv/bin/python build_ps4_pdf.py

Inputs (produced by the ps4_step*.py scripts, run them first):
    photos/                         handwritten pages (jpg/png/heic), included in filename order
    ps4_my_answers.txt              your written discussion answers (empty -> blank lined box)
    ndcp_2015_2022_metro.csv, cpi_u_annual.csv
    ps4_q2_summary_2022.csv, ps4_q2_histograms_2022.png
    ps4_q3_trends_by_year.csv, ps4_q3_real_price_trends.png
    ps4_q4_voucher_test.csv

Output:
    PS4_Lehman.pdf
"""
import re
import tempfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
from PIL import Image, ImageOps
import pillow_heif
from scipy import stats
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Flowable, Image as RLImage, KeepTogether, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

pillow_heif.register_heif_opener()
HERE = Path(__file__).parent
OUT = HERE / "PS4_Lehman.pdf"
PAGE_W, PAGE_H = letter
MARGIN = 0.8 * inch
TEXT_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------- styles
ss = getSampleStyleSheet()
BLUE = colors.HexColor("#1f4e8c")
MUTED = colors.HexColor("#6b6a64")
RULE = colors.HexColor("#c9c8c0")
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=17, textColor=BLUE, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, textColor=BLUE,
                    spaceBefore=10, spaceAfter=4)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10, leading=14, alignment=TA_LEFT)
QUESTION = ParagraphStyle("Q", parent=BODY, fontName="Helvetica-Oblique", textColor=MUTED,
                          leftIndent=10, spaceAfter=6)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8.5, leading=11, textColor=MUTED)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=9, leading=11)
MONO = ParagraphStyle("Mono", parent=BODY, fontName="Courier", fontSize=9, leading=12)


def P(text, style=BODY):
    return Paragraph(text, style)


def table(rows, col_widths=None, header=True, align_right_from=1):
    t = Table(rows, colWidths=col_widths, hAlign="LEFT", repeatRows=1 if header else 0)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.black),
        ("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if header:
        style += [("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                  ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.black)]
    t.setStyle(TableStyle(style))
    return t


def figure(path, width=TEXT_W):
    with Image.open(path) as im:
        w, h = im.size
    return RLImage(str(path), width=width, height=width * h / w)


# ---------------------------------------------------------------- answer boxes
class BlankAnswerBox(Flowable):
    """Bordered box with ruled lines for a handwritten or later answer."""

    def __init__(self, label, n_lines=10, line_gap=0.3 * inch):
        super().__init__()
        self.label, self.n_lines, self.line_gap = label, n_lines, line_gap
        self.width = TEXT_W
        self.height = 0.3 * inch + n_lines * line_gap

    def draw(self):
        c = self.canv
        c.setStrokeColor(RULE)
        c.setLineWidth(0.8)
        c.rect(0, 0, self.width, self.height)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(BLUE)
        c.drawString(8, self.height - 14, self.label)
        c.setLineWidth(0.4)
        for i in range(1, self.n_lines + 1):
            y = self.height - 0.3 * inch - i * self.line_gap + 0.12 * inch
            c.line(8, y, self.width - 8, y)


def subscripts(text):
    """Helvetica has no Unicode subscript digits; render them as <sub> markup."""
    for i, ch in enumerate("₀₁₂"):
        text = text.replace(ch, f"<sub>{i}</sub>")
    return text


def answer_box(key, label, answers, n_lines=10):
    text = answers.get(key, "").strip()
    if not text:
        return BlankAnswerBox(label, n_lines)
    paras = [P(f"<b>{escape(label)}</b>", ParagraphStyle("AL", parent=CELL, textColor=BLUE))]
    for block in re.split(r"\n\s*\n", text):
        paras.append(P(subscripts(escape(block.strip())).replace("\n", "<br/>"), BODY))
        paras.append(Spacer(1, 4))
    t = Table([[paras]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, RULE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def read_answers(path):
    answers, key, buf = {}, None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith("## "):
            if key:
                answers[key] = "\n".join(buf)
            key, buf = line[3:].strip(), []
        elif line.lstrip().startswith("#"):
            continue
        elif key:
            buf.append(line)
    if key:
        answers[key] = "\n".join(buf)
    return answers


# ---------------------------------------------------------------- photos
# Optional per-photo crop (left, top, right, bottom) as fractions of the image, to trim
# the tabletop around the notebook so the handwriting prints larger.
PHOTO_CROPS = {"IMG_7886.heic": (0.0, 0.145, 0.915, 0.915)}


def photo_flowables(tmpdir):
    files = sorted(p for p in (HERE / "photos").glob("*")
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic"})
    out = []
    max_w, max_h = TEXT_W, PAGE_H - 2 * MARGIN - 0.9 * inch
    for i, f in enumerate(files, 1):
        im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        if f.name in PHOTO_CROPS:
            l, t, r, b = PHOTO_CROPS[f.name]
            im = im.crop((int(l * im.width), int(t * im.height),
                          int(r * im.width), int(b * im.height)))
        im.thumbnail((2000, 2000))
        jpg = Path(tmpdir) / f"photo_{i}.jpg"
        im.save(jpg, quality=85)
        scale = min(max_w / im.width, max_h / im.height)
        out += [P(f"Handwritten work, page {i} of {len(files)}", SMALL), Spacer(1, 4),
                RLImage(str(jpg), width=im.width * scale, height=im.height * scale)]
        if i < len(files):
            out.append(PageBreak())
    return out, len(files)


# ---------------------------------------------------------------- page footer
def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 0.5 * inch, "MGT-403 - Problem Set 4")
    canvas.drawRightString(PAGE_W - MARGIN, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def money(x):
    return f"${x:,.2f}"


# ---------------------------------------------------------------- build
def build():
    answers = read_answers(HERE / "ps4_my_answers.txt")
    name = answers.get("name", "").strip() or "Name"

    metro = pd.read_csv(HERE / "ndcp_2015_2022_metro.csv", dtype={"fips": str, "oews_area": str})
    cpi = pd.read_csv(HERE / "cpi_u_annual.csv")
    q2 = pd.read_csv(HERE / "ps4_q2_summary_2022.csv")
    q3 = pd.read_csv(HERE / "ps4_q3_trends_by_year.csv")
    q4 = pd.read_csv(HERE / "ps4_q4_voucher_test.csv")
    groups = [("Infant", "mc_infant"), ("Toddler", "mc_toddler"), ("Preschool", "mc_preschool")]

    story = []
    tmp = tempfile.TemporaryDirectory()

    # Title
    story += [P("MGT-403 - Problem Set 4", H1),
              P(f"<b>{escape(name)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; {date.today():%B %d, %Y}", BODY),
              Spacer(1, 6),
              P("Part 1 is my handwritten work (photos). Part 2 answers the Data Project questions "
                "(Problem Set 4 - The Distribution of Childcare Prices) using the NDCP county "
                "workbook (NDCP2022.xlsx), the course-provided county_oews_crosswalk.csv, and BLS "
                "CPI-U. All numbers are produced by the Python scripts listed at the end and can "
                "be regenerated.", BODY),
              Spacer(1, 10)]

    # Part 1 - photos
    photos, n_photos = photo_flowables(tmp.name)
    story.append(PageBreak())
    story.append(P("Part 1 - Handwritten work", H2))
    if n_photos:
        story += photos
    else:
        story.append(P("<i>(No photos found in photos/.)</i>", BODY))
    story.append(PageBreak())

    # Part 2 header
    story.append(P("Part 2 - Data Project: The Distribution of Childcare Prices", H2))

    # ---- Q1
    story.append(P("Question 1 - Metro analysis sample", H3))
    story.append(P("Download the NDCP childcare price data. Restrict to the metro analysis sample "
                   "(counties in an OEWS metropolitan area) so PS4, PS5, and the final project use "
                   "a consistent county set.", QUESTION))
    n_counties = metro.groupby("year")["fips"].nunique()
    n_price = metro.groupby("year")["mc_preschool"].count()
    story.append(P(
        "<b>Steps.</b> (1) Read NDCP2022.xlsx with COUNTY_FIPS_CODE as text and zero-pad it to a "
        "5-character FIPS code. (2) Keep study years 2015-2022. (3) Merge on [fips, year] to "
        "county_oews_crosswalk.csv, with oews_area kept as a 7-character zero-padded string "
        "(the crosswalk is year-specific). (4) Keep counties whose oews_area begins with "
        "\"00\" (metropolitan) and drop non-metro codes. We focus on center-based median weekly "
        "prices (MCINFANT, MCTODDLER, MCPRESCHOOL)."))
    story.append(Spacer(1, 4))
    rows = [["Year", "Metro counties", "With center preschool price"]]
    rows += [[str(y), f"{n_counties[y]:,}", f"{n_price[y]:,}"] for y in n_counties.index]
    rows.append(["Total rows", f"{len(metro):,}", f"{metro['mc_preschool'].notna().sum():,}"])
    story.append(table(rows, [1.2 * inch, 1.4 * inch, 2.0 * inch]))
    story.append(Spacer(1, 4))
    n_pr = metro.loc[(metro["year"] == 2022) & (metro["STATE_ABBREVIATION"] == "PR"), "fips"].nunique()
    story.append(P(
        f"<b>Notes.</b> The metro sample has {len(metro):,} county-year rows and "
        f"{n_counties[2022]:,} counties in 2022, including {n_pr} Puerto Rico municipios "
        "(Puerto Rico has center-based prices only in 2021, so it does not affect the 2022 or 2015 "
        "analyses). Counties missing a price for an age group are dropped from that age group's "
        "statistics only. NDCP price flags (1/2/3) are retained but not used as a filter.", SMALL))

    # ---- Q2
    story.append(PageBreak())
    story.append(P("Question 2 - 2022 center-based prices by age group", H3))
    story.append(P("Using 2022: focusing on center-based care, make histograms of median prices by "
                   "child age group; report mean / SD / number of observations of prices. Compute "
                   "95% CIs for the average value within each age group. Based on your results, "
                   "discuss differences in prices across age groups.", QUESTION))
    story.append(figure(HERE / "ps4_q2_histograms_2022.png", width=5.4 * inch))
    story.append(Spacer(1, 6))
    rows = [["Age group", "N", "Mean", "SD", "SE", "95% CI for mean", "Median"]]
    for _, r in q2.iterrows():
        rows.append([r["age_group"], f"{int(r['n']):,}", money(r["mean"]), money(r["sd"]),
                     f"{r['se']:.2f}", f"[{money(r['ci_low'])}, {money(r['ci_high'])}]",
                     money(r["median"])])
    story.append(KeepTogether([
        P("<b>Table 2.</b> County median weekly center-based price, 2022 metro counties "
          "(nominal $).", CELL), Spacer(1, 3),
        table(rows, [0.95 * inch, 0.55 * inch, 0.75 * inch, 0.7 * inch, 0.5 * inch,
                     1.55 * inch, 0.75 * inch]),
        Spacer(1, 3),
        P("95% CI = mean &plusmn; t<sub>0.975, N-1</sub> &times; SD/&radic;N "
          "(t &asymp; 1.962).", SMALL)]))

    d22 = metro[metro["year"] == 2022].dropna(subset=[c for _, c in groups])
    rows = [["Comparison (same county)", "Mean difference", "95% CI", "Share of counties higher"]]
    for (la, ca), (lb, cb) in [(groups[0], groups[1]), (groups[1], groups[2]), (groups[0], groups[2])]:
        diff = d22[ca] - d22[cb]
        m, se = diff.mean(), diff.std(ddof=1) / np.sqrt(len(diff))
        h = stats.t.ppf(0.975, len(diff) - 1) * se
        rows.append([f"{la} - {lb}", money(m), f"[{money(m - h)}, {money(m + h)}]",
                     f"{(diff > 0).mean():.1%}"])
    story.append(Spacer(1, 8))
    story.append(KeepTogether([
        P(f"<b>Table 2b.</b> Within-county price differences, {len(d22):,} counties with all "
          "three prices (2022).", CELL), Spacer(1, 3),
        table(rows, [1.9 * inch, 1.2 * inch, 1.6 * inch, 1.6 * inch])]))
    story.append(Spacer(1, 10))
    story.append(answer_box("q2_discussion",
                            "Discussion - differences in prices across age groups", answers, 12))

    # ---- Q3
    story.append(PageBreak())
    story.append(P("Question 3 - Real prices over time (constant 2022 dollars)", H3))
    story.append(P("Convert all dollar values to constant 2022 dollars using CPI-U (CUUR0000SA0). "
                   "Plot trends in median price by year for each age group. Discuss: What has "
                   "happened to childcare prices over this period?", QUESTION))
    cpi22 = cpi.loc[cpi["year"] == 2022, "cpi_u"].item()
    story.append(P(
        "Real price<sub>t</sub> (2022 $) = nominal price<sub>t</sub> &times; "
        "CPI<sub>2022</sub> / CPI<sub>t</sub>, using CPI-U annual averages (BLS series "
        "CUUR0000SA0, U.S. city average, all items, 1982-84 = 100), retrieved from the BLS "
        "Public Data API. All six NDCP center-based price columns (median and 75th percentile) "
        "were converted."))
    story.append(Spacer(1, 4))
    rows = [["Year"] + [str(y) for y in cpi["year"]],
            ["CPI-U"] + [f"{v:.3f}" for v in cpi["cpi_u"]],
            ["2022 $ factor"] + [f"{cpi22 / v:.4f}" for v in cpi["cpi_u"]]]
    story.append(table(rows, [1.0 * inch] + [0.66 * inch] * len(cpi)))
    story.append(Spacer(1, 8))
    story.append(figure(HERE / "ps4_q3_real_price_trends.png"))
    story.append(Spacer(1, 4))
    story.append(P(
        "The set of counties reporting prices changes by year: 2021 drops counties in VA, NC, CA "
        "and PA and is the only year with Puerto Rico prices (about $78/week for preschool), which "
        "produces the 2021 dip in the left panel. The right panel is a balanced panel of counties "
        "with all three prices in every year, so its trend reflects price changes rather than "
        "sample changes.", SMALL))

    real = q3[q3["dollars"] == "real2022"]
    nom = q3[q3["dollars"] == "nominal"]
    for sample, title in [("balanced", "balanced panel"), ("all", "all reporting counties")]:
        r = real[real["sample"] == sample].pivot(index="year", columns="age_group", values="mean")
        nn = real[(real["sample"] == sample) & (real["age_group"] == "Preschool")].set_index("year")["n"]
        n = nom[nom["sample"] == sample].pivot(index="year", columns="age_group", values="mean")
        rows = [["Year", "Infant", "Toddler", "Preschool", "N (preschool)"]]
        for y in r.index:
            rows.append([str(y)] + [money(r.loc[y, g]) for g, _ in groups] + [f"{int(nn[y]):,}"])
        rows.append(["Real 2015-22"] + [f"{100 * (r.loc[2022, g] / r.loc[2015, g] - 1):+.1f}%"
                                        for g, _ in groups] + [""])
        rows.append(["Nominal 2015-22"] + [f"{100 * (n.loc[2022, g] / n.loc[2015, g] - 1):+.1f}%"
                                           for g, _ in groups] + [""])
        story.append(Spacer(1, 8))
        story.append(KeepTogether([
            P(f"<b>Table 3{'a' if sample == 'balanced' else 'b'}.</b> Mean county median weekly "
              f"price, 2022 dollars - {title}.", CELL), Spacer(1, 3),
            table(rows, [1.2 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.1 * inch])]))
    story.append(Spacer(1, 3))
    cpi_chg = 100 * (cpi22 / cpi.loc[cpi["year"] == 2015, "cpi_u"].item() - 1)
    story.append(P(f"CPI-U rose {cpi_chg:.1f}% from 2015 to 2022.", SMALL))
    story.append(Spacer(1, 10))
    story.append(answer_box("q3_discussion",
                            "Discussion - what has happened to childcare prices?", answers, 12))

    # ---- Q4
    story.append(PageBreak())
    story.append(P("Question 4 - Does the CCDF voucher equal the median center-based preschool "
                   "price?", H3))
    story.append(P("In 2022 the monthly CCDF voucher for center-based preschool was $706 (2015: "
                   "$473, nominal). ACF asserts that in the average metro area this voucher equals "
                   "the price of care at the median-priced center-based preschool. Assuming 4.33 "
                   "weeks per month, test this at the 5% level.", QUESTION))
    c22 = q4[(q4["unit"] == "county") & (q4["year"] == 2022)].iloc[0]
    c15 = q4[(q4["unit"] == "county") & (q4["year"] == 2015)].iloc[0]

    story.append(P("<b>(a) Hypotheses.</b> Let &mu; be the mean, across metro counties, of the "
                   "county median weekly center-based preschool price (2022 nominal $). The "
                   f"weekly value of the voucher is $706 / 4.33 = {money(c22['mu0_weekly'])}.",
                   BODY))
    story.append(P(f"H<sub>0</sub>: &mu; = {c22['mu0_weekly']:.2f} &nbsp;&nbsp;&nbsp; versus "
                   f"&nbsp;&nbsp;&nbsp; H<sub>1</sub>: &mu; &ne; {c22['mu0_weekly']:.2f} "
                   "&nbsp;&nbsp; (two-sided, &alpha; = 0.05)",
                   ParagraphStyle("hyp", parent=BODY, leftIndent=24, spaceBefore=3, spaceAfter=6)))

    story.append(P("<b>(b) Test statistic.</b> One-sample t-test:", BODY))
    story.append(P("t = ( x-bar - &mu;<sub>0</sub> ) / ( s / &radic;n ), &nbsp;&nbsp; which "
                   "follows a t distribution with n - 1 degrees of freedom under H<sub>0</sub>.",
                   ParagraphStyle("f", parent=BODY, leftIndent=24, spaceBefore=3, spaceAfter=6)))
    total = metro.loc[metro["year"] == 2022, "mc_preschool"].sum()
    rows = [["Element", "Calculation", "Value"],
            ["n", "counties with a 2022 center preschool price", f"{int(c22['n']):,}"],
            ["x-bar (sample mean)", f"{total:,.2f} / {int(c22['n']):,}", money(c22["mean"])],
            ["μ0 (null value)", "706 / 4.33", money(c22["mu0_weekly"])],
            ["x-bar - μ0", f"{c22['mean']:.2f} - {c22['mu0_weekly']:.2f}",
             money(c22["mean"] - c22["mu0_weekly"])],
            ["s (sample SD)", "√[ Σ(x - x-bar)² / (n - 1) ]", money(c22["sd"])],
            ["√n", f"√{int(c22['n']):,}", f"{np.sqrt(c22['n']):.4f}"],
            ["SE = s / √n", f"{c22['sd']:.4f} / {np.sqrt(c22['n']):.4f}", f"{c22['se']:.4f}"],
            ["t", f"{c22['mean'] - c22['mu0_weekly']:.4f} / {c22['se']:.4f}",
             f"{c22['t_manual']:.4f}"],
            ["Critical value", f"t(0.975, df = {int(c22['df'])})", f"±{c22['t_crit']:.4f}"]]
    story.append(table(rows, [1.6 * inch, 3.2 * inch, 1.2 * inch], align_right_from=2))

    story.append(Spacer(1, 8))
    story.append(P("<b>(c) Statistical package and p-value.</b> Computed with Python "
                   "<font face='Courier'>scipy.stats.ttest_1samp(x, popmean=706/4.33)</font> "
                   "(two-sided). The p-value is the probability, under H<sub>0</sub>, of a t "
                   "statistic at least this far from zero in either direction:", BODY))
    story.append(P("p = 2 &times; P( T<sub>n-1</sub> &ge; |t| ) = 2 &times; [ 1 - "
                   "F<sub>t, n-1</sub>( |t| ) ]",
                   ParagraphStyle("f2", parent=BODY, leftIndent=24, spaceBefore=3, spaceAfter=6)))
    ok = np.isclose(c22["t_manual"], c22["t_scipy"])
    rows = [["", "Manual (b)", "scipy"],
            ["t statistic", f"{c22['t_manual']:.4f}", f"{c22['t_scipy']:.4f}"],
            ["p-value", f"{2 * stats.t.sf(abs(c22['t_manual']), c22['df']):.2e}",
             f"{c22['p_value']:.2e}"],
            ["95% CI for μ", "", f"[{money(c22['ci_low'])}, {money(c22['ci_high'])}]"]]
    story.append(table(rows, [1.6 * inch, 1.4 * inch, 2.0 * inch]))
    story.append(Spacer(1, 3))
    story.append(P(f"The manual and package t statistics {'match' if ok else 'DO NOT match'} "
                   "(the script asserts equality to machine precision).", SMALL))

    story.append(Spacer(1, 8))
    rows = [["", "2022", "2015"],
            ["Monthly voucher (nominal)", "$706", "$473"],
            ["μ0 = voucher / 4.33 (weekly)", money(c22["mu0_weekly"]), money(c15["mu0_weekly"])],
            ["n", f"{int(c22['n']):,}", f"{int(c15['n']):,}"],
            ["Mean weekly price x-bar", money(c22["mean"]), money(c15["mean"])],
            ["SD s", money(c22["sd"]), money(c15["sd"])],
            ["SE", f"{c22['se']:.4f}", f"{c15['se']:.4f}"],
            ["t statistic", f"{c22['t_manual']:.3f}", f"{c15['t_manual']:.3f}"],
            ["p-value (two-sided)", f"{c22['p_value']:.2e}", f"{c15['p_value']:.2e}"],
            ["95% CI for μ", f"[{money(c22['ci_low'])}, {money(c22['ci_high'])}]",
             f"[{money(c15['ci_low'])}, {money(c15['ci_high'])}]"],
            ["Mean price, monthly (x-bar × 4.33)", money(c22["mean"] * 4.33),
             money(c15["mean"] * 4.33)],
            ["Share of counties priced above voucher", f"{c22['share_above_voucher']:.1%}",
             f"{c15['share_above_voucher']:.1%}"]]
    story.append(KeepTogether([
        P("<b>Table 4.</b> Test results, 2022 and 2015 (county level, nominal dollars of each "
          "year).", CELL), Spacer(1, 3),
        table(rows, [2.6 * inch, 1.7 * inch, 1.7 * inch])]))
    story.append(Spacer(1, 3))
    a22 = q4[(q4["unit"] == "metro_area") & (q4["year"] == 2022)].iloc[0]
    a15 = q4[(q4["unit"] == "metro_area") & (q4["year"] == 2015)].iloc[0]
    story.append(P(
        f"Robustness: averaging counties within each OEWS metro area ({int(a22['n'])} areas) and "
        f"testing the area averages gives t = {a22['t_scipy']:.2f} (p = {a22['p_value']:.1e}) in "
        f"2022 and t = {a15['t_scipy']:.2f} (p = {a15['p_value']:.1e}) in 2015.", SMALL))
    story.append(Spacer(1, 10))
    story.append(answer_box("q4d_interpretation",
                            "(d) Interpretation - do you reject H0, and why? What happens with "
                            "2015 data and subsidy levels?", answers, 12))

    # ---- Reproducibility
    story.append(PageBreak())
    ai_note = answers.get("ai_use", "").strip()
    if ai_note:
        story.append(P("Note on AI use", H3))
        for block in re.split(r"\n\s*\n", ai_note):
            story += [P(subscripts(escape(block.strip())).replace("\n", " "), BODY), Spacer(1, 4)]
        story.append(Spacer(1, 8))
    story.append(P("Appendix - Code and reproducibility", H3))
    story.append(P("Run from the PS4 folder, using the project virtual environment in the parent "
                   "folder (pandas, numpy, scipy, matplotlib, reportlab). The raw inputs "
                   "(NDCP2022.xlsx, county_oews_crosswalk.csv) sit in the parent folder.", BODY))
    for line in ["python ps4_step1_metro_sample.py ../NDCP2022.xlsx ../county_oews_crosswalk.csv",
                 "python ps4_step2_histograms_2022.py",
                 "python ps4_step3_real_trends.py",
                 "python ps4_step4_ccdf_voucher_test.py",
                 "python build_ps4_pdf.py"]:
        story.append(P(escape(line), MONO))
    story.append(Spacer(1, 6))
    rows = [["Script", "Purpose", "Main outputs"],
            ["ps4_step1_metro_sample.py", "Q1: 2015-22, FIPS padding, OEWS metro filter",
             "ndcp_2015_2022_metro.csv"],
            ["ps4_step2_histograms_2022.py", "Q2: histograms, mean/SD/N, 95% CIs",
             "ps4_q2_histograms_2022.png, ps4_q2_summary_2022.csv"],
            ["ps4_step3_real_trends.py", "Q3: CPI-U deflation, trends",
             "ndcp_2015_2022_metro_real.csv, ps4_q3_*.png/.csv"],
            ["ps4_step4_ccdf_voucher_test.py", "Q4: one-sample t-tests", "ps4_q4_voucher_test.csv"],
            ["build_ps4_pdf.py", "Assembles this document", OUT.name]]
    rows = [[P(escape(c), CELL) for c in r] for r in rows]
    story.append(table(rows, [2.0 * inch, 2.3 * inch, 2.6 * inch], align_right_from=99))

    doc = SimpleDocTemplate(str(OUT), pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN,
                            title="MGT-403 Problem Set 4", author=name)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    tmp.cleanup()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
