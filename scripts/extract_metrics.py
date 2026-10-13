"""Extract quarterly metrics from Spotify shareholder decks into a CSV.

Reads data/raw/<YYYY>_Q<n>.pdf and writes data/quarterly_metrics.csv.
Every value comes from the deck for that quarter, as reported. Nothing is
estimated or derived. If a metric can't be found unambiguously it's left
blank and listed in the output.

Sources inside each deck:
  - "User, Financial & Liquidity Summary" table (last quarter column):
    total MAUs, Premium subscribers, Premium revenue, Ad-Supported revenue,
    total gross margin
  - IFRS condensed consolidated statement of operations (first column):
    sales and marketing, operating income
  - Narrative text: Premium ARPU, Premium and Ad-Supported gross margin
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
    ("premium_revenue_eur_m", "Premium revenue (€M)"),
    ("ad_supported_revenue_eur_m", "Ad-Supported revenue (€M)"),
    ("premium_arpu_eur", "Premium ARPU (€)"),
    ("premium_gross_margin_pct", "Premium gross margin (%)"),
    ("ad_supported_gross_margin_pct", "Ad-Supported gross margin (%)"),
    ("total_gross_margin_pct", "Total gross margin (%)"),
    ("sales_and_marketing_eur_m", "Sales & marketing (€M)"),
    ("operating_income_eur_m", "Operating income (€M)"),
]

QUARTER_END = {1: "March 31", 2: "June 30", 3: "September 30", 4: "December 31"}

# Summary-table row label -> output column. Labels may carry footnote asterisks.
SUMMARY_ROWS = {
    r'Total Monthly Active Users \("MAUs"\)': "total_maus_m",
    r"Premium Subscribers": "premium_subscribers_m",
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


def parse_summary_table(pages, year, q, notes):
    """Current-quarter values from the 5-quarter summary table."""
    label = f"Q{q} {year}"
    for text in pages:
        lines = text.splitlines()
        header = next(
            (i for i, l in enumerate(lines) if re.match(r"USER, FINANCIAL.*SUMMARY", l)), None
        )
        if header is None:
            continue
        quarters = re.findall(r"Q[1-4] \d{4}", lines[header])
        if not quarters or quarters[-1] != label:
            notes.append(f"summary table header {quarters} does not end in {label}")
            return {}
        col = len(quarters) - 1
        found = {}
        for line in lines[header + 1 :]:
            for pattern, key in SUMMARY_ROWS.items():
                m = re.match(rf"{pattern}\**((?: {NUM})+)", line)
                if not m or key in found:
                    continue
                values = m.group(1).split()
                if len(values) > col:
                    found[key] = to_number(values[col])
        return found
    notes.append("summary table not found")
    return {}


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


def parse_narrative(pages, notes):
    text = re.sub(r"\s+", " ", " ".join(pages))
    return {
        "premium_arpu_eur": unique_match(
            r"ARPU\W[^€]{0,90}€ ?(\d+\.\d+)", text, "premium_arpu_eur", notes
        ),
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

    return f"{year}_Q{q}", row, notes


def fmt(value):
    if value is None:
        return ""
    return f"{value:g}"


def main():
    pdfs = sorted(RAW_DIR.glob("[0-9][0-9][0-9][0-9]_Q[1-4].pdf"))
    if not pdfs:
        sys.exit(f"No decks found in {RAW_DIR}")

    results = [extract(p) for p in pdfs]

    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["quarter"] + [key for key, _ in COLUMNS] + ["source_file"])
        for (quarter, row, _), pdf in zip(results, pdfs):
            writer.writerow([quarter] + [fmt(row[key]) for key, _ in COLUMNS] + [pdf.relative_to(ROOT)])

    short = ["MAUs", "Subs", "Prem rev", "Ad rev", "ARPU", "Prem GM%", "Ad GM%", "GM%", "S&M", "Op inc"]
    widths = [max(len(h), 7) for h in short]
    print("quarter  " + "  ".join(h.rjust(w) for h, w in zip(short, widths)))
    for quarter, row, _ in results:
        cells = [(fmt(row[key]) or "—").rjust(w) for (key, _), w in zip(COLUMNS, widths)]
        print(f"{quarter}  " + "  ".join(cells))
    print("\nUnits: MAUs/subs in millions; revenue, S&M, operating income in €M; ARPU in €; margins in %.")

    print("\nMissing metrics:")
    any_missing = False
    for quarter, row, _ in results:
        missing = [label for key, label in COLUMNS if row[key] is None]
        if missing:
            any_missing = True
            print(f"  {quarter}: {', '.join(missing)}")
    if not any_missing:
        print("  none")

    print("\nExtraction notes:")
    notes = [(quarter, n) for quarter, _, ns in results for n in ns]
    for quarter, n in notes:
        print(f"  {quarter}: {n}")
    if not notes:
        print("  none")

    print(f"\nWrote {len(results)} rows to {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
