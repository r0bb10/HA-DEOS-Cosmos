"""COSMOS request payloads and response decoders.

DO04-DO11 bit positions are inferred and have not been hardware-verified.
"""

import math
import struct
from html.parser import HTMLParser

ANALOG_INPUT_PAYLOAD = """0;SPS_MERK;30;932;
1;SPS_VARI;60;4512;
2;SPS_VARI;108;4610;
3;SPS_VARI;8;4670;
4;SPS_VARI;108;4870;
5;SPS_VARI;4;4924;"""

DIGITAL_OUTPUT_PAYLOAD = """0;SPS_MERK;109;1045;
1;SPS_MERK;4;1156;"""

ANALOG_INPUT_MAP = {
    0: ("AI00", "sonda mandata climatizzazione"),
    2: ("AI01", "sonda ritorno climatizzazione"),
    3: ("AI02", "sonda accumulo climatizzazione"),
    5: ("AI03", "sonda ritorno carico boyler"),
    6: ("AI04", "sonda accumulo ACS"),
    8: ("AI05", "sonda ricircolo ACS"),
    9: ("AI06", "sonda primario scambiatore CLIMATIZZ."),
    11: ("AI07", "sonda secondario scambiatore CLIMATIZZ."),
}
DIGITAL_OUTPUT_MAP = {
    0: ("DO00", "abilitazione PdC 1"),
    1: ("DO01", "abilitazione PdC 2"),
    2: ("DO02", "comando EP 1 Climatizz."),
    3: ("DO03", "comando EP 2 Climatizz."),
    **{index: (f"DO{index:02}", "reserve") for index in range(4, 12)},
}


class ProtocolError(ValueError):
    """The controller returned an invalid or unexpected response."""


def _rows(text: str) -> dict[int, str]:
    lines = text.strip().splitlines()
    if not lines or lines[0].strip() != "OK":
        raise ProtocolError("unexpected_response")
    rows: dict[int, str] = {}
    for line in lines[1:]:
        parts = line.strip().split(";")
        if len(parts) < 5:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            continue
        if index in rows:
            raise ProtocolError("duplicate_response_row")
        rows[index] = parts[4]
    return rows


def decode_analog(text: str) -> dict[str, float | None]:
    data = _rows(text).get(4, "")
    result: dict[str, float | None] = {}
    for index, (channel, _) in ANALOG_INPUT_MAP.items():
        chunk = data[index * 8 : (index + 1) * 8]
        value = None
        if len(chunk) == 8:
            try:
                decoded = struct.unpack(">f", bytes.fromhex(chunk))[0]
                if math.isfinite(decoded) and -50 < decoded < 150:
                    value = decoded
            except ValueError, struct.error:
                pass
        result[channel] = value
    return result


def decode_digital(text: str) -> dict[str, bool | None]:
    rows = _rows(text)
    result: dict[str, bool | None] = {}
    for index, (channel, _) in DIGITAL_OUTPUT_MAP.items():
        row = 0 if index < 10 else 1
        pos = 163 + index * 6 if row == 0 else 1 + (index - 10) * 6
        bits = rows.get(row, "")
        # Invalid characters invalidate the row; short rows only invalidate missing bits.
        valid = bool(bits) and all(bit in "01" for bit in bits)
        result[channel] = bits[pos] == "1" if valid and pos < len(bits) else None
    return result


class _InfoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: list[str] = []
        self.cell: list[str] | None = None
        self.info: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.cells = []
        elif tag in {"td", "th"}:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and len(self.cells) >= 2:
            mapping = {
                "hardware type": "model",
                "hardware version": "hw_version",
                "firmware version": "sw_version",
                "serial number": "serial_number",
                "mac address": "mac_address",
            }
            if (key := mapping.get(self.cells[0].lower())) and self.cells[1]:
                self.info[key] = self.cells[1]


def decode_system_info(html: str) -> dict[str, str]:
    parser = _InfoParser()
    parser.feed(html)
    if not parser.info:
        raise ProtocolError("missing_system_info")
    return parser.info
