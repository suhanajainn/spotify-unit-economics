"""Extract quarterly metrics from Spotify shareholder decks into a CSV.

Reads data/raw/<YYYY>_Q<n>.pdf and writes data/quarterly_metrics.csv.
Every value comes from the deck for that quarter, as reported. Nothing is
estimated or derived. If a metric can't be found unambiguously it's left
blank and listed in the output.

Sources inside each deck:
  - "User, Financial & Liquidity Summary" table (last quarter column):
    total MAUs, Premium subscribers, Ad-Supported MAUs, Premium revenue, Ad-Supported revenue,
    total gross margin
  - IFRS condensed consolidated statement of operations (first column):
    sales and marketing, operating income
  - Narrative text: Premium ARPU, Premium and Ad-Supported gross margin

Effective 2026-01-01 Spotify moved some activities from Ad-Supported to
Premium. The as-reported segment columns use whichever definition was in
force for that quarter (see reported_segment_basis). The *_restated columns
are all on the 2026 definition, taken from the 2026 decks; quarters the
decks don't restate in text are left blank.
"""

import csv
import logging
import re
import sys
from pathlib import Path

import pdfplumber

logging.getLogger("pdfminer").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_CSV = ROOT / "data" / "quarterly_metrics.csv"

COLUMNS = [
    ("total_maus_m", "Total MAUs (M)"),
    ("premium_subscribers_m", "Premium subscribers (M)"),
    ("ad_supported_maus_m", "Ad-Supported MAUs (M)"),
    ("premium_revenue_eur_m", "Premium revenue (€M)"),
    ("ad_supported_revenue_eur_m", "Ad-Supported revenue (€M)"),
    ("premium_arpu_eur", "Premium ARPU (€)"),
    ("premium_arpu_yoy_constant_currency_pct", "Premium ARPU Y/Y, constant currency (%)"),
    ("premium_gross_margin_pct", "Premium gross margin (%)"),
    ("ad_supported_gross_margin_pct", "Ad-Supported gross margin (%)"),
    ("total_gross_margin_pct", "Total gross margin (%)"),
    ("sales_and_marketing_eur_m", "Sales & marketing (€M)"),
    ("operating_income_eur_m", "Operating income (€M)"),
    ("premium_revenue_restated_eur_m", "Restated Premium revenue (€M)"),
    ("ad_supported_revenue_restated_eur_m", "Restated Ad-Supported revenue (€M)"),
    ("premium_gross_margin_restated_pct", "Restated Premium gross margin (%)"),
    ("ad_supported_gross_margin_restated_pct", "Restated Ad-Supported gross margin (%)"),
    ("opex_social_charges_eur_m", "Social Charges in operating expenses (€M)"),
]

# Effective 2026-01-01 Spotify moved some activities from Ad-Supported to Premium.
# Decks for quarters from this one onward report segments on the new basis.
RECLASS_FROM = (2026, 1)

# Values for the reported_segment_basis column: which segment definition the
# as-reported Premium/Ad-Supported columns use. Restated columns are always "2026".
BASIS_ORIGINAL = "pre-2026 (original)"
BASIS_2026 = "2026 (reclassified)"

# Restated column -> matching as-reported column.
RESTATED = {
    "premium_revenue_restated_eur_m": "premium_revenue_eur_m",
    "ad_supported_revenue_restated_eur_m": "ad_supported_revenue_eur_m",
    "premium_gross_margin_restated_pct": "premium_gross_margin_pct",
    "ad_supported_gross_margin_restated_pct": "ad_supported_gross_margin_pct",
}

QUARTER_END = {1: "March 31", 2: "June 30", 3: "September 30", 4: "December 31"}

# Summary-table row label -> output column. Labels may carry footnote asterisks.
SUMMARY_ROWS = {
    r'Total Monthly Active Users \("MAUs"\)': "total_maus_m",
    r"Premium Subscribers": "premium_subscribers_m",
    r"Ad-Supported MAUs": "ad_supported_maus_m",
    r"Premium": "premium_revenue_eur_m",
    r"Ad-Supported": "ad_supported_revenue_eur_m",
    r"Gross Margin": "total_gross_margin_pct",
}

NUM = r"\(?-?[\d,]+(?:\.\d+)?%?\)?"


def to_number(token):
    """Parse '1,234', '(75)', '33.4%' into a float. Parentheses mean negative."""
    neg = token.startswith("(") and token.endswith(")")
    value = float(token.strip("()%").replace(",", ""))
    return -value if neg else value


def page_texts(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def summary_table(pages):
    """All columns of the 5-quarter summary table: {"Q1 2026": {key: value}}."""
    for text in pages:
        lines = text.splitlines()
        header = next(
            (i for i, l in enumerate(lines) if re.match(r"USER, FINANCIAL.*SUMMARY", l)), None
        )
        if header is None:
            continue
        quarters = re.findall(r"Q[1-4] \d{4}", lines[header])
        table = {quarter: {} for quarter in quarters}
        for line in lines[header + 1 :]:
            for pattern, key in SUMMARY_ROWS.items():
                m = re.match(rf"{pattern}\**((?: {NUM})+)", line)
                if not m or key in table[quarters[-1]]:
                    continue
                values = m.group(1).split()
                if len(values) >= len(quarters):
                    for quarter, value in zip(quarters, values):
                        table[quarter][key] = to_number(value)
        return table
    return None


def parse_summary_table(pages, year, q, notes):
    """Current-quarter values from the 5-quarter summary table."""
    label = f"Q{q} {year}"
    table = summary_table(pages)
    if table is None:
        notes.append("summary table not found")
        return {}
    quarters = list(table)
    if not quarters or quarters[-1] != label:
        notes.append(f"summary table header {quarters} does not end in {label}")
        return {}
    return table[label]


def segment_reclassification_table(pages):
    """Restated segment figures from the 'Segment Reclassification' appendix.

    Returns {"Q1 2024": {key: value}}, quarterly columns only (annual totals dropped).
    """
    for text in pages:
        lines = text.splitlines()
        header = next(
            (i for i, l in enumerate(lines) if l.startswith("SEGMENT RECLASSIFICATION")), None
        )
        if header is None:
            continue
        columns = re.findall(r"Q[1-4] \d{4}|\d{4}", lines[header])
        table = {c: {} for c in columns if c.startswith("Q")}
        previous = ""
        for line in lines[header + 1 :]:
            key = None
            if re.match(r"Premium\*? \d", line):
                key = "premium_revenue_restated_eur_m"
            elif re.match(r"Ad-Supported\*? \d", line):
                key = "ad_supported_revenue_restated_eur_m"
            elif line.startswith("Gross Margin (%)") and previous.startswith("Premium Gross Profit"):
                key = "premium_gross_margin_restated_pct"
            elif line.startswith("Gross Margin (%)") and previous.startswith("Ad-Supported Gross Profit"):
                key = "ad_supported_gross_margin_restated_pct"
            elif line.startswith("Total Gross Margin (%)"):
                key = "total_gross_margin_pct"
            previous = line
            if key is None:
                continue
            values = re.findall(NUM, line)
            if len(values) != len(columns):
                continue
            for column, value in zip(columns, values):
                if column in table:
                    table[column][key] = to_number(value)
        return table
    return None


def parse_income_statement(pages, year, q, notes):
    """Current-quarter values from the IFRS statement of operations."""
    for text in pages:
        if not re.search(r"statement of operations", text, re.I) or "Three months ended" not in text:
            continue
        dates = re.search(r"Three months ended.*\n(\w+ \d+), (\d{4})", text)
        if not dates or dates.groups() != (QUARTER_END[q], str(year)):
            notes.append(f"income statement first column is {dates and dates.groups()}, expected {QUARTER_END[q]}, {year}")
            return {}
        found = {}
        for key, pattern in (
            ("revenue", r"^Revenue"),
            ("sales_and_marketing_eur_m", r"^Sales and marketing"),
            ("operating_income_eur_m", r"^Operating (?:income|\(loss\)|loss)\S*"),
        ):
            m = re.search(rf"{pattern} ({NUM})", text, re.M)
            if m:
                found[key] = to_number(m.group(1))
        return found
    notes.append("statement of operations not found")
    return {}


def unique_match(pattern, text, key, notes):
    """Return the single distinct value matched by pattern, or None if 0 or >1."""
    values = {float(v) for v in re.findall(pattern, text)}
    if len(values) == 1:
        return values.pop()
    if len(values) > 1:
        notes.append(f"{key}: ambiguous matches {sorted(values)}")
    return None


def arpu_constant_currency(text, notes):
    """Y/Y Premium ARPU growth in constant currency, as stated next to ARPU.

    Phrasings seen: "(or down 1% constant currency", "(or up 5.7% Y/Y constant
    currency", "(or 7.4% Y/Y constant currency", "(or flat Y/Y constant currency".
    """
    values = set()
    for m in re.finditer(r"ARPU\W[^€]{0,90}€ ?\d+\.\d+[^()]{0,20}\(or ([^)]*?)constant currency", text):
        phrase = m.group(1)
        if re.match(r"flat\b", phrase):
            values.add(0.0)
            continue
        n = re.match(r"(up |down )?(\d+(?:\.\d+)?)%", phrase)
        if n:
            values.add(-float(n.group(2)) if n.group(1) == "down " else float(n.group(2)))
    if len(values) == 1:
        return values.pop()
    if len(values) > 1:
        notes.append(f"premium_arpu_yoy_constant_currency_pct: ambiguous matches {sorted(values)}")
    return None


def parse_narrative(pages, notes):
    text = re.sub(r"\s+", " ", " ".join(pages))
    return {
        "premium_arpu_eur": unique_match(
            r"ARPU\W[^€]{0,90}€ ?(\d+\.\d+)", text, "premium_arpu_eur", notes
        ),
        "premium_arpu_yoy_constant_currency_pct": arpu_constant_currency(text, notes),
        "premium_gross_margin_pct": unique_match(
            r"Premium Gross Margin\** (?:was|of) (\d+(?:\.\d+)?)%", text, "premium_gross_margin_pct", notes
        ),
        "ad_supported_gross_margin_pct": unique_match(
            r"Ad-Supported Gross Margin\** (?:was|of) (\d+(?:\.\d+)?)%", text, "ad_supported_gross_margin_pct", notes
        ),
    }


def extract(pdf_path):
    year, q = re.fullmatch(r"(\d{4})_Q([1-4])", pdf_path.stem).groups()
    year, q = int(year), int(q)
    notes = []
    pages = page_texts(pdf_path)

    row = {key: None for key, _ in COLUMNS}
    row.update(parse_summary_table(pages, year, q, notes))
    statement = parse_income_statement(pages, year, q, notes)
    revenue = statement.pop("revenue", None)
    row.update(statement)
    row.update({k: v for k, v in parse_narrative(pages, notes).items() if v is not None})

    # Cross-check: segment revenues should sum to IFRS total revenue.
    prem, ad = row["premium_revenue_eur_m"], row["ad_supported_revenue_eur_m"]
    if None not in (prem, ad, revenue) and prem + ad != revenue:
        notes.append(f"segment revenue {prem:,.0f} + {ad:,.0f} != IFRS revenue {revenue:,.0f}")

    return f"{year}_Q{q}", row, notes, pages


def add_restated(results, pdfs):
    """Fill restated segment columns on the post-2026 basis.

    Candidate values come from (a) the Segment Reclassification appendix,
    (b) prior-quarter columns in new-basis decks' summary tables, and (c) a
    new-basis deck's own current-quarter figures. A value is kept only if all
    candidates agree; otherwise it's left blank and noted.
    """
    candidates = {}  # (quarter, key) -> {value: [source, ...]}

    def offer(quarter, key, value, source):
        candidates.setdefault((quarter, key), {}).setdefault(value, []).append(source)

    for (quarter, row, notes, pages), pdf in zip(results, pdfs):
        year, q = int(quarter[:4]), int(quarter[-1])
        if (year, q) < RECLASS_FROM:
            continue
        for restated_key, reported_key in RESTATED.items():
            if row[reported_key] is not None:
                offer(quarter, restated_key, row[reported_key], pdf.name)

        reclass = segment_reclassification_table(pages) or {}
        summary = summary_table(pages) or {}
        for label, values in reclass.items():
            target = label[-4:] + "_Q" + label[1]
            for key in RESTATED:
                if key in values:
                    offer(target, key, values[key], f"{pdf.name} segment reclassification")
            # Sanity check: total gross margin isn't affected by the reclassification.
            for _, other_row, other_notes, _ in (r for r in results if r[0] == target):
                total = values.get("total_gross_margin_pct")
                if total is not None and other_row["total_gross_margin_pct"] not in (None, total):
                    other_notes.append(
                        f"{pdf.name} reclassification table total GM {total} != reported {other_row['total_gross_margin_pct']}"
                    )
        for label, values in list(summary.items())[:-1]:
            target = label[-4:] + "_Q" + label[1]
            for restated_key, reported_key in RESTATED.items():
                if reported_key in values:
                    offer(target, restated_key, values[reported_key], f"{pdf.name} summary table")

    for quarter, row, notes, _ in results:
        sources = set()
        for key in RESTATED:
            options = candidates.get((quarter, key), {})
            if len(options) == 1:
                (value, srcs), = options.items()
                row[key] = value
                sources.update(s.split()[0] for s in srcs)
            elif len(options) > 1:
                notes.append(f"{key}: sources disagree {options}")
        row["restated_source"] = "; ".join(sorted(sources))


def add_social_charges(results):
    """Social Charges (payroll taxes on share-based comp) in operating expenses.

    Spotify states this for the current quarter and, a year later, as the
    prior-year comparison. It is a total across R&D, S&M and G&A; the decks
    don't split it by line. A value is kept only if every statement agrees.
    Statements that don't say the amount is in Operating Expenses are ignored.
    """
    candidates = {}
    current = [
        r"(?<!Prior year period )Operating Expenses included (\(?€\s?\d+\)?) million in Social Charges",
        r"Social Charges related to share-based compensation of €(\d+) million in (?:the )?current period Operating Expenses",
        r"Social Charges related to share-based compensation of €\d+ million in the current period, €(\d+) million of which were in Operating Expenses",
    ]
    prior = r"Prior year period Operating Expenses included (\(?€\s?\d+\)?) million in Social Charges"
    for quarter, _, _, pages in results:
        text = re.sub(r"\s+", " ", " ".join(pages))
        year, q = int(quarter[:4]), quarter[-2:]
        for pattern in current:
            for m in re.finditer(pattern, text):
                candidates.setdefault(quarter, set()).add(to_number(m.group(1).replace("€", "")))
        for m in re.finditer(prior, text):
            candidates.setdefault(f"{year - 1}_{q}", set()).add(to_number(m.group(1).replace("€", "")))
    for quarter, row, notes, _ in results:
        values = candidates.get(quarter, set())
        if len(values) == 1:
            row["opex_social_charges_eur_m"] = values.pop()
        elif len(values) > 1:
            notes.append(f"opex_social_charges_eur_m: sources disagree {sorted(values)}")


def fmt(value):
    if value is None:
        return ""
    return f"{value:g}"


def main():
    pdfs = sorted(RAW_DIR.glob("[0-9][0-9][0-9][0-9]_Q[1-4].pdf"))
    if not pdfs:
        sys.exit(f"No decks found in {RAW_DIR}")

    results = [extract(p) for p in pdfs]
    add_restated(results, pdfs)
    add_social_charges(results)

    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["quarter", "reported_segment_basis"]
            + [key for key, _ in COLUMNS]
            + ["source_file", "restated_source"]
        )
        for (quarter, row, _, _), pdf in zip(results, pdfs):
            year, q = int(quarter[:4]), int(quarter[-1])
            basis = BASIS_2026 if (year, q) >= RECLASS_FROM else BASIS_ORIGINAL
            writer.writerow(
                [quarter, basis]
                + [fmt(row[key]) for key, _ in COLUMNS]
                + [pdf.relative_to(ROOT), row["restated_source"]]
            )

    def print_table(title, keys, headers):
        widths = [max(len(h), 7) for h in headers]
        print(title)
        print("quarter  " + "  ".join(h.rjust(w) for h, w in zip(headers, widths)))
        for quarter, row, _, _ in results:
            cells = [(fmt(row[key]) or "—").rjust(w) for key, w in zip(keys, widths)]
            print(f"{quarter}  " + "  ".join(cells))

    keys = [key for key, _ in COLUMNS]
    print_table(
        "As reported in each quarter's deck",
        keys[:12],
        ["MAUs", "Subs", "Ad MAUs", "Prem rev", "Ad rev", "ARPU", "ARPU cc%", "Prem GM%", "Ad GM%", "GM%", "S&M", "Op inc"],
    )
    print()
    print_table(
        "Segments restated to the 2026 basis",
        keys[12:16],
        ["Prem rev", "Ad rev", "Prem GM%", "Ad GM%"],
    )
    print("\nUnits: MAUs/subs in millions; revenue, S&M, operating income in €M; ARPU in €; margins in %.")

    print("\nMissing metrics:")
    any_missing = False
    for quarter, row, _, _ in results:
        missing = [label for key, label in COLUMNS if row[key] is None]
        if missing:
            any_missing = True
            print(f"  {quarter}: {', '.join(missing)}")
    if not any_missing:
        print("  none")

    print("\nExtraction notes:")
    notes = [(quarter, n) for quarter, _, ns, _ in results for n in ns]
    for quarter, n in notes:
        print(f"  {quarter}: {n}")
    if not notes:
        print("  none")

    print(f"\nWrote {len(results)} rows to {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
