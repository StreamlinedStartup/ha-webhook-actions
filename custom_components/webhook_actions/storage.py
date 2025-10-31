"""Storage handler for webhook configurations."""
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_WEBHOOK_ID,
    CONF_WEBHOOKS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class WebhookStorage:
    """Manage webhook configuration storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize storage handler."""
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {CONF_WEBHOOKS: {}}

    async def async_load(self) -> None:
        """Load webhook configurations from storage."""
        data = await self.store.async_load()
        if data:
            self.data = data
        _LOGGER.debug("Loaded %d webhooks from storage", len(self.data.get(CONF_WEBHOOKS, {})))

    async def async_save(self) -> None:
        """Save webhook configurations to storage."""
        await self.store.async_save(self.data)
        _LOGGER.debug("Saved %d webhooks to storage", len(self.data.get(CONF_WEBHOOKS, {})))

    async def async_add_webhook(self, webhook_id: str, config: dict[str, Any]) -> None:
        """Add or update a webhook configuration."""
        if CONF_WEBHOOKS not in self.data:
            self.data[CONF_WEBHOOKS] = {}

        self.data[CONF_WEBHOOKS][webhook_id] = config
        await self.async_save()
        _LOGGER.info("Added/updated webhook: %s", webhook_id)

    async def async_remove_webhook(self, webhook_id: str) -> None:
        """Remove a webhook configuration."""
        if webhook_id in self.data.get(CONF_WEBHOOKS, {}):
            del self.data[CONF_WEBHOOKS][webhook_id]
            await self.async_save()
            _LOGGER.info("Removed webhook: %s", webhook_id)

    def get_webhook(self, webhook_id: str) -> dict[str, Any] | None:
        """Get a webhook configuration by ID."""
        return self.data.get(CONF_WEBHOOKS, {}).get(webhook_id)

    def get_all_webhooks(self) -> dict[str, dict[str, Any]]:
        """Get all webhook configurations."""
        return self.data.get(CONF_WEBHOOKS, {})

    def webhook_exists(self, webhook_id: str) -> bool:
        """Check if a webhook ID exists."""
        return webhook_id in self.data.get(CONF_WEBHOOKS, {})


class WebhookConfigManager:
    """Manage webhook configurations from both YAML and UI sources."""

    def __init__(
        self,
        hass: HomeAssistant,
        yaml_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize configuration manager."""
        self.hass = hass
        self.yaml_config = yaml_config or {}
        self.storage = WebhookStorage(hass)

    async def async_setup(self) -> None:
        """Set up the configuration manager."""
        await self.storage.async_load()

    def get_all_webhooks(self) -> dict[str, dict[str, Any]]:
        """Get all webhook configurations (merged YAML and UI configs)."""
        webhooks = {}

        # Start with YAML configs
        if CONF_WEBHOOKS in self.yaml_config:
            for webhook in self.yaml_config[CONF_WEBHOOKS]:
                webhook_id = webhook.get(CONF_WEBHOOK_ID)
                if webhook_id:
                    webhooks[webhook_id] = webhook.copy()

        # Overlay UI configs (they take precedence)
        ui_webhooks = self.storage.get_all_webhooks()
        webhooks.update(ui_webhooks)

        return webhooks

    def get_webhook(self, webhook_id: str) -> dict[str, Any] | None:
        """Get a specific webhook configuration."""
        # Check UI config first (higher priority)
        ui_webhook = self.storage.get_webhook(webhook_id)
        if ui_webhook:
            return ui_webhook

        # Fall back to YAML config
        if CONF_WEBHOOKS in self.yaml_config:
            for webhook in self.yaml_config[CONF_WEBHOOKS]:
                if webhook.get(CONF_WEBHOOK_ID) == webhook_id:
                    return webhook.copy()

        return None

    async def async_add_webhook(self, webhook_id: str, config: dict[str, Any]) -> None:
        """Add or update a webhook configuration in UI storage."""
        await self.storage.async_add_webhook(webhook_id, config)

    async def async_remove_webhook(self, webhook_id: str) -> None:
        """Remove a webhook configuration from UI storage."""
        await self.storage.async_remove_webhook(webhook_id)

    def webhook_exists(self, webhook_id: str) -> bool:
        """Check if a webhook ID exists in either YAML or UI config."""
        # Check UI storage
        if self.storage.webhook_exists(webhook_id):
            return True

        # Check YAML config
        if CONF_WEBHOOKS in self.yaml_config:
            for webhook in self.yaml_config[CONF_WEBHOOKS]:
                if webhook.get(CONF_WEBHOOK_ID) == webhook_id:
                    return True

        return False
