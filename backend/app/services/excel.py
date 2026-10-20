"""Excel exports: one workbook builder for every statistics page.

Each page that shows figures has an `export.xlsx` twin that runs the *same*
service call and lays its result out here, so a sheet never carries a number
the screen would not -- and an instructor's export, built from the instructor's
service, cannot carry a column only an admin should see.

Conventions every sheet follows (`Sheet`):

* a caption above the table: what the report is, the period it covers, when it
  was exported -- a spreadsheet forwarded by email has nothing else around it;
* one bold header row, frozen, with a filter on it;
* numbers stay numbers. Money is written as a number with a "₫" format rather
  than as the string "1.200.000 ₫", so the sheet can still be summed; rates are
  fractions shown as percentages; times are Vietnamese local time.

**User text is never a formula.** openpyxl stores any string that starts with
"=" as a formula, and a course called "=HYPERLINK(...)" would then run in the
admin's Excel. Every text cell is forced to a string cell.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Literal
from urllib.parse import quote

from fastapi import Response
from openpyxl import Workbook
from openpyxl.cell.cell import TYPE_STRING
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.vnpay import VIETNAM

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

Kind = Literal["text", "number", "int", "money", "rate", "decimal", "date", "datetime"]

FORMATS: dict[str, str] = {
    "number": "General",
    "int": "#,##0",
    "money": '#,##0 "₫"',
    "rate": "0.0%",
    "decimal": "#,##0.00",
    "date": "dd/mm/yyyy",
    "datetime": "dd/mm/yyyy hh:mm",
}
DEFAULT_WIDTHS: dict[str, int] = {
    "text": 28,
    "number": 14,
    "int": 12,
    "money": 18,
    "rate": 12,
    "decimal": 12,
    "date": 13,
    "datetime": 18,
}

HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill("solid", fgColor="E8EEF7")
TITLE_FONT = Font(bold=True, size=14)
TOTAL_FONT = Font(bold=True)
#: Excel's own limit on a sheet name, and the characters it refuses in one.
SHEET_TITLE_MAX = 31
SHEET_TITLE_FORBIDDEN = set("[]:*?/\\")


@dataclass(frozen=True, slots=True)
class Column:
    header: str
    kind: Kind = "text"
    width: int | None = None


@dataclass(frozen=True, slots=True)
class Cell:
    """A value whose format is not its column's -- a summary sheet that lists
    counts, sums of money and rates in one "value" column."""

    value: Any
    kind: Kind


def money_cell(value: Any) -> Cell:
    return Cell(value, "money")


def rate_cell(value: Any) -> Cell:
    return Cell(value, "rate")


@dataclass(slots=True)
class Sheet:
    title: str
    columns: Sequence[Column]
    rows: Sequence[Sequence[Any]]
    #: Lines above the table; the first is the report's name.
    caption: Sequence[str] = field(default_factory=list)
    #: An optional last row, in bold -- usually sums.
    totals: Sequence[Any] | None = None


def exported_at_line(now: datetime | None = None) -> str:
    moment = (now or datetime.now(VIETNAM)).astimezone(VIETNAM)
    return f"Xuất lúc {moment:%H:%M %d/%m/%Y} (giờ Việt Nam)"


def _sheet_title(title: str, taken: set[str]) -> str:
    clean = "".join(" " if char in SHEET_TITLE_FORBIDDEN else char for char in title).strip()
    clean = (clean or "Sheet")[:SHEET_TITLE_MAX]
    candidate, n = clean, 2
    while candidate.lower() in taken:
        suffix = f" ({n})"
        candidate = clean[: SHEET_TITLE_MAX - len(suffix)] + suffix
        n += 1
    taken.add(candidate.lower())
    return candidate


def _value(value: Any, kind: Kind) -> Any:
    if value is None:
        return None
    if kind == "datetime" and isinstance(value, datetime):
        # Excel has no time zones: write the Vietnamese wall clock.
        return value.astimezone(VIETNAM).replace(tzinfo=None) if value.tzinfo else value
    if kind in ("money", "decimal") and not isinstance(value, Decimal):
        return Decimal(str(value))
    return value


def _write_row(ws, row_index: int, columns: Sequence[Column], values: Sequence[Any]) -> list:
    cells = []
    for column_index, (column, raw) in enumerate(zip(columns, values, strict=True), start=1):
        kind = column.kind
        if isinstance(raw, Cell):
            raw, kind = raw.value, raw.kind
        cell = ws.cell(row=row_index, column=column_index, value=_value(raw, kind))
        if isinstance(cell.value, str):
            # See the module docstring: user text must never become a formula.
            cell.data_type = TYPE_STRING
        elif kind in FORMATS:
            cell.number_format = FORMATS[kind]
        cells.append(cell)
    return cells


def build(sheets: Sequence[Sheet]) -> bytes:
    """The workbook, as the bytes of an .xlsx file."""
    if not sheets:
        raise ValueError("a workbook needs at least one sheet")
    book = Workbook()
    book.remove(book.active)
    taken: set[str] = set()

    for sheet in sheets:
        ws = book.create_sheet(_sheet_title(sheet.title, taken))
        row = 1
        for index, line in enumerate(sheet.caption):
            cell = ws.cell(row=row, column=1, value=line)
            cell.data_type = TYPE_STRING
            if index == 0:
                cell.font = TITLE_FONT
            row += 1
        if sheet.caption:
            row += 1  # one blank line between the caption and the table

        header_row = row
        for column_index, column in enumerate(sheet.columns, start=1):
            cell = ws.cell(row=header_row, column=column_index, value=column.header)
            cell.data_type = TYPE_STRING
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            width = column.width or DEFAULT_WIDTHS[column.kind]
            ws.column_dimensions[get_column_letter(column_index)].width = width

        for values in sheet.rows:
            row += 1
            _write_row(ws, row, sheet.columns, values)

        last_data_row = row
        if sheet.totals is not None:
            row += 1
            for cell in _write_row(ws, row, sheet.columns, sheet.totals):
                cell.font = TOTAL_FONT

        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
        last_column = get_column_letter(len(sheet.columns))
        ws.auto_filter.ref = f"A{header_row}:{last_column}{max(last_data_row, header_row)}"

    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def response(content: bytes, filename: str) -> Response:
    """An .xlsx download. `filename` may be Vietnamese; the ASCII fallback is
    for clients that do not read `filename*`."""
    ascii_name = filename.encode("ascii", "ignore").decode() or "bao-cao.xlsx"
    ascii_name = ascii_name.replace('"', "")
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            ),
            "Cache-Control": "no-store",
        },
    )


def day_range_line(start: date, end: date) -> str:
    return f"Kỳ báo cáo: {start:%d/%m/%Y} – {end:%d/%m/%Y} (giờ Việt Nam)"
