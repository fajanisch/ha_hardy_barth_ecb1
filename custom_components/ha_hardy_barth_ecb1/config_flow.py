"""Config Flow für die Hardy Barth eCB1 Integration."""
from __future__ import annotations

import asyncio
from typing import Any
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class ECB1ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow für eCB1 Wallbox."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)

            try:
                # Verbindung testen mit dem /all Endpunkt
                async with session.get(f"http://{host}/api/v1/all", timeout=10) as response:
                    if response.status != 200:
                        errors["base"] = "cannot_connect"
                    else:
                        # Testen ob es echtes JSON ist
                        await response.json()
            except (asyncio.TimeoutError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except (ValueError, TypeError):
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"eCB1 ({host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )