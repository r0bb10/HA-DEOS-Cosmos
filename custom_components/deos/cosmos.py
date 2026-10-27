"""Asynchronous COSMOS HTTP client."""

import hashlib
import ipaddress
import re
import time
from dataclasses import dataclass

from aiohttp import ClientError, ClientSession, ClientTimeout
from yarl import URL

from .const import DEFAULT_INFO_PORT, DEFAULT_PORT, MAX_RESPONSE_BYTES, REQUEST_TIMEOUT
from .protocol import ProtocolError, decode_system_info


class CosmosError(Exception):
    """A safe diagnostic code, never a raw response or URL."""


def normalize_host(value: str) -> str:
    """Accept an IP or DNS hostname, never a URL or embedded port."""
    if not isinstance(value, str):
        raise ValueError("invalid_host")
    host = value.strip().lower().rstrip(".")
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        if (
            not host
            or len(host) > 253
            or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in host.split(".")
            )
        ):
            raise ValueError("invalid_host") from None
    return host


def normalize_port(value: int | float) -> int:
    if type(value) not in {int, float} or not 1 <= value <= 65535 or int(value) != value:
        raise ValueError("invalid_port")
    return int(value)


def serial_number(info: dict[str, str]) -> str | None:
    serial = info.get("serial_number", "").strip()
    return serial if serial.lower() not in {"", "unknown", "none", "n/a"} else None


@dataclass(frozen=True, slots=True)
class Connection:
    host: str
    port: int = DEFAULT_PORT
    info_port: int = DEFAULT_INFO_PORT

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", normalize_host(self.host))
        object.__setattr__(self, "port", normalize_port(self.port))
        object.__setattr__(self, "info_port", normalize_port(self.info_port))

    @property
    def configuration_url(self) -> str:
        return str(URL.build(scheme="http", host=self.host, port=self.info_port))

    def identity(self, info: dict[str, str]) -> str:
        if serial := serial_number(info):
            return f"cosmos_{serial}"
        digest = hashlib.sha256(f"{self.host}:{self.port}".encode()).hexdigest()[:16]
        return f"deos_{digest}"


class CosmosClient:
    """Reuse HA's session. The coordinator owns retries, scheduling, and lifecycle."""

    def __init__(self, session: ClientSession, connection: Connection) -> None:
        self._session = session
        self.connection = connection

    async def _request(self, payload: str | None = None) -> str:
        url = URL.build(
            scheme="http",
            host=self.connection.host,
            port=self.connection.port if payload is not None else self.connection.info_port,
            path="/cgi-bin/cosmobdf.cgi" if payload is not None else "/sysinfo.htm",
        )
        try:
            async with self._session.request(
                "POST" if payload is not None else "GET",
                url,
                params={"function": "25", "t": str(int(time.time() * 1000))} if payload else None,
                data=payload,
                skip_auto_headers={"Content-Type"},
                allow_redirects=False,
                raise_for_status=False,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT, ceil_threshold=60),
            ) as response:
                if response.status != 200:
                    raise CosmosError(f"http_{response.status}")
                body = bytearray()
                async for chunk in response.content.iter_chunked(16384):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise CosmosError("response_too_large")
                return body.decode(response.charset or "utf-8").strip()
        except TimeoutError:
            raise CosmosError("request_timeout") from None
        except ClientError:
            raise CosmosError("connection_failed") from None
        except UnicodeError, LookupError:
            raise CosmosError("invalid_text_encoding") from None

    async def async_read(self, payload: str) -> str:
        return await self._request(payload)

    async def async_get_system_info(self) -> dict[str, str]:
        try:
            return decode_system_info(await self._request())
        except ProtocolError as err:
            raise CosmosError(str(err)) from None
