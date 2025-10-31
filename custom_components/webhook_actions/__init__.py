"""The Webhook Actions integration."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_HEADERS,
    CONF_HEADERS_OVERRIDE,
    CONF_METHOD,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PAYLOAD_OVERRIDE,
    CONF_RETRY_ATTEMPTS,
    CONF_TIMEOUT,
    CONF_TIMEOUT_OVERRIDE,
    CONF_URL,
    CONF_URL_OVERRIDE,
    CONF_WEBHOOK_ID,
    CONF_WEBHOOKS,
    DEFAULT_METHOD,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    HTTP_METHODS,
    SERVICE_CALL,
)
from .storage import WebhookConfigManager
from .webhook import WebhookExecutor

_LOGGER = logging.getLogger(__name__)

# YAML configuration schema
WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WEBHOOK_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(HTTP_METHODS),
        vol.Optional(CONF_HEADERS, default={}): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_PAYLOAD): vol.Any(cv.string, dict, list),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(
            CONF_RETRY_ATTEMPTS, default=DEFAULT_RETRY_ATTEMPTS
        ): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_WEBHOOKS, default=[]): vol.All(
                    cv.ensure_list, [WEBHOOK_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Webhook Actions component from YAML."""
    hass.data.setdefault(DOMAIN, {})

    # Store YAML config
    yaml_config = config.get(DOMAIN, {})
    hass.data[DOMAIN]["yaml_config"] = yaml_config

    # Initialize config manager
    config_manager = WebhookConfigManager(hass, yaml_config)
    await config_manager.async_setup()
    hass.data[DOMAIN]["config_manager"] = config_manager

    # Register service
    await async_setup_services(hass, config_manager)

    _LOGGER.info(
        "Webhook Actions initialized with %d webhooks",
        len(config_manager.get_all_webhooks()),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Webhook Actions from a config entry."""
    # Ensure component is set up
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Initialize config manager if not already done
    if "config_manager" not in hass.data[DOMAIN]:
        config_manager = WebhookConfigManager(hass)
        await config_manager.async_setup()
        hass.data[DOMAIN]["config_manager"] = config_manager

        # Register service if not already registered
        if not hass.services.has_service(DOMAIN, SERVICE_CALL):
            await async_setup_services(hass, config_manager)

    # Add webhook to config manager
    config_manager: WebhookConfigManager = hass.data[DOMAIN]["config_manager"]
    await config_manager.async_add_webhook(
        entry.data[CONF_WEBHOOK_ID],
        entry.data,
    )

    # Update listener for config changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Webhook entry added: %s", entry.data[CONF_NAME])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Remove webhook from config manager
    config_manager: WebhookConfigManager = hass.data[DOMAIN]["config_manager"]
    await config_manager.async_remove_webhook(entry.data[CONF_WEBHOOK_ID])

    _LOGGER.info("Webhook entry removed: %s", entry.data[CONF_NAME])

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options when config entry is updated."""
    config_manager: WebhookConfigManager = hass.data[DOMAIN]["config_manager"]
    await config_manager.async_add_webhook(
        entry.data[CONF_WEBHOOK_ID],
        entry.data,
    )
    _LOGGER.info("Webhook entry updated: %s", entry.data[CONF_NAME])


async def async_setup_services(
    hass: HomeAssistant, config_manager: WebhookConfigManager
) -> None:
    """Set up webhook services."""

    async def handle_webhook_call(call: ServiceCall) -> ServiceResponse:
        """Handle webhook call service."""
        webhook_id = call.data[CONF_WEBHOOK_ID]

        # Get webhook config
        webhook_config = config_manager.get_webhook(webhook_id)
        if not webhook_config:
            raise HomeAssistantError(f"Webhook '{webhook_id}' not found")

        # Extract overrides
        url_override = call.data.get(CONF_URL_OVERRIDE)
        headers_override = call.data.get(CONF_HEADERS_OVERRIDE)
        payload_override = call.data.get(CONF_PAYLOAD_OVERRIDE)
        timeout_override = call.data.get(CONF_TIMEOUT_OVERRIDE)

        # Execute webhook
        executor = WebhookExecutor(hass, webhook_config)

        try:
            response = await executor.execute(
                url_override=url_override,
                headers_override=headers_override,
                payload_override=payload_override,
                timeout_override=timeout_override,
            )

            _LOGGER.debug(
                "Webhook %s executed successfully: HTTP %s",
                webhook_id,
                response["status_code"],
            )

            return response

        except Exception as err:
            _LOGGER.error("Webhook %s execution failed: %s", webhook_id, err)
            raise HomeAssistantError(f"Webhook execution failed: {err}") from err

    # Service schema
    service_schema = vol.Schema(
        {
            vol.Required(CONF_WEBHOOK_ID): cv.string,
            vol.Optional(CONF_URL_OVERRIDE): cv.string,
            vol.Optional(CONF_HEADERS_OVERRIDE): vol.Schema({cv.string: cv.string}),
            vol.Optional(CONF_PAYLOAD_OVERRIDE): vol.Any(cv.string, dict, list),
            vol.Optional(CONF_TIMEOUT_OVERRIDE): cv.positive_int,
        }
    )

    # Register service
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALL,
        handle_webhook_call,
        schema=service_schema,
        supports_response=SupportsResponse.OPTIONAL,
    )

    _LOGGER.info("Webhook Actions services registered")
