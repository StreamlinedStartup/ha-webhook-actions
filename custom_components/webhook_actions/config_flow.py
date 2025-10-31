"""Config flow for Webhook Actions integration."""
import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_HEADERS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_RETRY_ATTEMPTS,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_WEBHOOK_ID,
    DEFAULT_METHOD,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    HTTP_METHODS,
)

_LOGGER = logging.getLogger(__name__)


class WebhookActionsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Webhook Actions."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            webhook_id = user_input[CONF_WEBHOOK_ID]
            url = user_input[CONF_URL]

            # Check if webhook ID already exists
            if self._webhook_id_exists(webhook_id):
                errors[CONF_WEBHOOK_ID] = "webhook_id_exists"
            # Validate URL format
            elif not self._is_valid_url(url):
                errors[CONF_URL] = "invalid_url"
            else:
                # Create entry
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_WEBHOOK_ID: webhook_id,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_URL: user_input[CONF_URL],
                        CONF_METHOD: user_input.get(CONF_METHOD, DEFAULT_METHOD),
                        CONF_HEADERS: user_input.get(CONF_HEADERS, {}),
                        CONF_PAYLOAD: user_input.get(CONF_PAYLOAD),
                        CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                        CONF_RETRY_ATTEMPTS: user_input.get(
                            CONF_RETRY_ATTEMPTS, DEFAULT_RETRY_ATTEMPTS
                        ),
                    },
                )

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_WEBHOOK_ID): str,
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_URL): str,
                vol.Required(CONF_METHOD, default=DEFAULT_METHOD): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=HTTP_METHODS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_HEADERS): selector.ObjectSelector(),
                vol.Optional(CONF_PAYLOAD): selector.ObjectSelector(),
                vol.Optional(
                    CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=300,
                        unit_of_measurement="seconds",
                    )
                ),
                vol.Optional(
                    CONF_RETRY_ATTEMPTS, default=DEFAULT_RETRY_ATTEMPTS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=10,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    def _webhook_id_exists(self, webhook_id: str) -> bool:
        """Check if webhook ID already exists."""
        # Check in config entries
        for entry in self._async_current_entries():
            if entry.data.get(CONF_WEBHOOK_ID) == webhook_id:
                return True
        return False

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ["http", "https"]
        except Exception:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "WebhookActionsOptionsFlow":
        """Get the options flow for this handler."""
        return WebhookActionsOptionsFlow(config_entry)


class WebhookActionsOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Webhook Actions."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL]

            # Validate URL format
            if not self._is_valid_url(url):
                errors[CONF_URL] = "invalid_url"
            else:
                # Update config entry (including title shown in UI)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=user_input[CONF_NAME],
                    data={
                        **self.config_entry.data,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_URL: user_input[CONF_URL],
                        CONF_METHOD: user_input[CONF_METHOD],
                        CONF_HEADERS: user_input.get(CONF_HEADERS, {}),
                        CONF_PAYLOAD: user_input.get(CONF_PAYLOAD),
                        CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                        CONF_RETRY_ATTEMPTS: user_input[CONF_RETRY_ATTEMPTS],
                    },
                )
                return self.async_create_entry(title="", data={})

        # Pre-fill with current values
        current_data = self.config_entry.data
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=current_data.get(CONF_NAME)
                ): str,
                vol.Required(
                    CONF_URL, default=current_data.get(CONF_URL)
                ): str,
                vol.Required(
                    CONF_METHOD,
                    default=current_data.get(CONF_METHOD, DEFAULT_METHOD),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=HTTP_METHODS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_HEADERS,
                    default=current_data.get(CONF_HEADERS, {}),
                ): selector.ObjectSelector(),
                vol.Optional(
                    CONF_PAYLOAD,
                    default=current_data.get(CONF_PAYLOAD),
                ): selector.ObjectSelector(),
                vol.Optional(
                    CONF_TIMEOUT,
                    default=current_data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=300,
                        unit_of_measurement="seconds",
                    )
                ),
                vol.Optional(
                    CONF_RETRY_ATTEMPTS,
                    default=current_data.get(CONF_RETRY_ATTEMPTS, DEFAULT_RETRY_ATTEMPTS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=10,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "webhook_id": current_data.get(CONF_WEBHOOK_ID, "unknown")
            },
        )

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ["http", "https"]
        except Exception:
            return False
