"""Config flow for Alpha Private Speaker."""
from __future__ import annotations

import voluptuous as vol
from typing import Any
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_GRPC_PORT,
    CONF_EVENT_PREFIX,
    CONF_MAX_SPEAKERS,
    CONF_HA_TOKEN,
    CONF_HA_URL,
    DEFAULT_GRPC_PORT,
    DEFAULT_EVENT_PREFIX,
    DEFAULT_MAX_SPEAKERS,
    DEFAULT_HA_URL
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Alpha Private Speaker."""
    
    VERSION = 1
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            # Для упрощения пропускаем проверку соединения на первом этапе
            # Пользователь может настроить соединение позже
            return self.async_create_entry(
                title="Alpha Private Speaker Connector",
                data=user_input
            )
        
        # Показываем форму
        data_schema = vol.Schema({
            vol.Required(CONF_HA_TOKEN): str,
            vol.Required(CONF_HA_URL, default=DEFAULT_HA_URL): str,
            vol.Required(CONF_GRPC_PORT, default=DEFAULT_GRPC_PORT): cv.port,
            vol.Optional(CONF_EVENT_PREFIX, default=DEFAULT_EVENT_PREFIX): str,
            vol.Optional(CONF_MAX_SPEAKERS, default=DEFAULT_MAX_SPEAKERS): cv.positive_int,
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/VGCH/alpha-private-speaker-connector"
            }
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Alpha Speaker."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
    
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update config entry
            return self.async_create_entry(title="", data=user_input)
        
        # Show current values
        options_schema = vol.Schema({
            vol.Required(
                CONF_GRPC_PORT,
                default=self.config_entry.options.get(CONF_GRPC_PORT, DEFAULT_GRPC_PORT)
            ): cv.port,
            vol.Optional(
                CONF_EVENT_PREFIX,
                default=self.config_entry.options.get(CONF_EVENT_PREFIX, DEFAULT_EVENT_PREFIX)
            ): str,
            vol.Optional(
                CONF_MAX_SPEAKERS,
                default=self.config_entry.options.get(CONF_MAX_SPEAKERS, DEFAULT_MAX_SPEAKERS)
            ): cv.positive_int,
            vol.Optional(
                CONF_HA_URL,
                default=self.config_entry.options.get(CONF_HA_URL, DEFAULT_HA_URL)
            ): str,
        })
        
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema
        )