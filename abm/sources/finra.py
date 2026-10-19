"""FINRA margin statistics (monthly spreadsheet), parsed without extra libraries."""

import io
import re
import zipfile

from . import get

URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"


def fetch():
    """Margin debit balances in $ millions, dated the first of each month."""
    z = zipfile.ZipFile(io.BytesIO(get(URL).content))
    xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    out = []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
        month = re.search(r'<c r="A\d+"[^>]*><is><t>(\d{4}-\d{2})</t></is></c>', row)
        debit = re.search(r'<c r="B\d+"[^>]*><v>([\d.]+)</v></c>', row)
        if month and debit:
            out.append((month.group(1) + "-01", float(debit.group(1))))
    if not out:
        raise RuntimeError("FINRA margin sheet: no rows parsed")
    return sorted(out)
