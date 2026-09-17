"""API Client für die Hardy Barth eCB1 Integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class ECB1ApiClientError(Exception):
    """Ausnahme, wenn ein API-Fehler auftritt."""


class ECB1ApiClient:
    """API-Client zum Abrufen der eCB1 Daten."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        """Initialize."""
        self._host = host
        self._session = session

    async def async_get_data(self) -> dict[str, Any]:
        """Ruft alle System-, Meter- und Wallbox-Daten von der eCB1 API ab."""
        return await self._api_wrapper(
            method="get",
            url=f"http://{self._host}/api/v1/all",
        )

    async def _api_wrapper(self, method: str, url: str, data: dict | None = None) -> dict[str, Any]:
        """Wrapper für API-Requests mit Fehlerbehandlung."""
        try:
            async with asyncio.timeout(10):
                response = await self._session.request(
                    method,
                    url,
                    json=data,
                )
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError as exception:
            raise ECB1ApiClientError(
                f"Zeitüberschreitung bei der Verbindung zu {url}"
            ) from exception
        except aiohttp.ClientError as exception:
            raise ECB1ApiClientError(
                f"Fehler bei der Kommunikation mit der eCB1 API ({url}): {exception}"
            ) from exception
        except Exception as exception:
            raise ECB1ApiClientError(
                f"Unerwarteter Fehler bei der API-Abfrage: {exception}"
            ) from exception