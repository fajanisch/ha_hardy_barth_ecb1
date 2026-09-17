"""DataUpdateCoordinator für die Hardy Barth eCB1 Integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ECB1ApiClient, ECB1ApiClientError
from .const import _LOGGER, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)


class ECB1DataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Klasse zur Verwaltung des Abrufs der eCB1 Daten."""

    def __init__(self, hass: HomeAssistant, api: ECB1ApiClient, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = api
        self.config_entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Ruft Daten von der API ab."""
        try:
            return await self.api.async_get_data()
        except ECB1ApiClientError as error:
            raise UpdateFailed(f"Fehler beim Abrufen der eCB1 Daten: {error}") from error