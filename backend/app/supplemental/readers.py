"""Read Salesforce's HTML exports without treating .xls as a binary workbook."""
from html.parser import HTMLParser
from io import BytesIO
import pandas as pd
import re


class ExportTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None
        self.depth, self.done = 0, False

    def handle_starttag(self, tag, attrs):
        if tag == "table" and not self.done:
            self.depth += 1
        if self.depth == 1:
            if tag == "tr":
                self.row = []
            elif tag in {"td", "th"}:
                self.cell = []
            elif tag == "br" and self.cell is not None:
                self.cell.append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.depth == 1:
            if tag in {"td", "th"} and self.cell is not None:
                if self.row is not None:
                    self.row.append("".join(self.cell).strip())
                self.cell = None
            elif tag == "tr" and self.row is not None:
                if self.row:
                    self.rows.append(self.row)
                self.row = None
        if tag == "table" and self.depth:
            self.depth -= 1
            self.done = self.depth == 0


def salesforce(raw):
    if not raw.lstrip().startswith(b"<"):
        return pd.read_excel(BytesIO(raw))
    parser = ExportTable()
    declared = re.search(br"charset\s*=\s*[\"']?([\w-]+)", raw[:1024], re.I)
    encoding = declared[1].decode("ascii").lower() if declared else "utf-8-sig"
    if encoding not in {"utf-8", "utf-8-sig", "iso-8859-1", "windows-1252"}:
        raise ValueError("unsupported_encoding")
    parser.feed(raw.decode(encoding))
    if not parser.rows or len(set(parser.rows[0])) != len(parser.rows[0]):
        raise ValueError("invalid_header")
    columns = parser.rows[0]
    if any(len(row) != len(columns) for row in parser.rows[1:]):
        raise ValueError("invalid_row_width")
    return pd.DataFrame(parser.rows[1:], columns=columns).replace("", None)


def survey(raw):
    header = pd.read_csv(BytesIO(raw), nrows=2)
    # Check for Qualtrics metadata before skipping it; do not discard real rows.
    if "ResponseId" not in header or len(header) < 2 or "ImportId" not in str(header.iloc[1].get("ResponseId")):
        raise ValueError("invalid_qualtrics_header")
    return pd.read_csv(BytesIO(raw), skiprows=[1, 2])
