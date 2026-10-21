"""Config flow for Vacuula."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VacuulaClient, VacuulaError
from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN


class VacuulaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the address of the Vacuula server."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            client = VacuulaClient(async_get_clientsession(self.hass), host, port)
            try:
                await client.get_server_info()
            except VacuulaError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Vacuula ({host})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(user_input or {}).get(CONF_HOST, DEFAULT_HOST),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT),
                    ): vol.All(int, vol.Range(min=1, max=65535)),
                }
            ),
            errors=errors,
        )
