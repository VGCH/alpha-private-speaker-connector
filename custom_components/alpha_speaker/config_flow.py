"""Config flow для Alpha Connector."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

try:
    # Актуальный API Home Assistant.
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # Совместимость со старыми версиями HA.
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

from .const import (
    DOMAIN,
    NAME,
    CONF_GRPC_PORT,
    CONF_EVENT_PREFIX,
    CONF_MAX_SPEAKERS,
    DEFAULT_GRPC_PORT,
    DEFAULT_EVENT_PREFIX,
    DEFAULT_MAX_SPEAKERS,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Настройка единственного локального gRPC-коннектора."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Показать и обработать форму первичной настройки."""
        # Интеграция поднимает один локальный gRPC-сервер,
        # поэтому второй config entry не допускается.
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            _LOGGER.debug("Получены настройки Alpha Connector")
            return self.async_create_entry(title=NAME, data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_GRPC_PORT,
                    default=DEFAULT_GRPC_PORT,
                ): cv.port,
                vol.Optional(
                    CONF_EVENT_PREFIX,
                    default=DEFAULT_EVENT_PREFIX,
                ): vol.All(cv.string, vol.Length(min=1, max=64)),
                vol.Optional(
                    CONF_MAX_SPEAKERS,
                    default=DEFAULT_MAX_SPEAKERS,
                ): vol.All(cv.positive_int, vol.Range(min=1, max=100)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders={
                "docs_url": "https://github.com/VGCH/alpha-private-speaker-connector"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Создать обработчик параметров интеграции."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Изменение параметров gRPC-сервера."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Показать и обработать форму параметров."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_GRPC_PORT,
                    default=current.get(CONF_GRPC_PORT, DEFAULT_GRPC_PORT),
                ): cv.port,
                vol.Optional(
                    CONF_EVENT_PREFIX,
                    default=current.get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX),
                ): vol.All(cv.string, vol.Length(min=1, max=64)),
                vol.Optional(
                    CONF_MAX_SPEAKERS,
                    default=current.get(CONF_MAX_SPEAKERS, DEFAULT_MAX_SPEAKERS),
                ): vol.All(cv.positive_int, vol.Range(min=1, max=100)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
