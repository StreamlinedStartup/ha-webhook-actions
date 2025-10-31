"""Webhook execution logic for Webhook Actions."""
import asyncio
import json
import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.template import Template

from .const import (
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PAYLOAD,
    CONF_RETRY_ATTEMPTS,
    CONF_RETRY_BACKOFF,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_WEBHOOK_ID,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_TIMEOUT,
    ERROR_CONNECTION,
    ERROR_HTTP,
    ERROR_TEMPLATE,
    ERROR_TIMEOUT,
    EVENT_WEBHOOK_ERROR,
    EVENT_WEBHOOK_SUCCESS,
    MAX_RESPONSE_SIZE,
)

_LOGGER = logging.getLogger(__name__)


class WebhookExecutor:
    """Handle webhook execution with retry logic and template support."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize webhook executor."""
        self.hass = hass
        self.config = config
        self.session = async_get_clientsession(hass)

    async def execute(
        self,
        url_override: str | None = None,
        headers_override: dict[str, str] | None = None,
        payload_override: Any | None = None,
        timeout_override: int | None = None,
    ) -> dict[str, Any]:
        """Execute webhook with retry logic."""
        webhook_id = self.config.get(CONF_WEBHOOK_ID, "unknown")

        # Build final configuration with overrides
        url = url_override or self.config.get(CONF_URL)
        method = self.config.get(CONF_METHOD, "POST")
        headers = self.config.get(CONF_HEADERS, {}).copy()

        if headers_override:
            headers.update(headers_override)

        payload = payload_override if payload_override is not None else self.config.get(CONF_PAYLOAD)
        # Ensure numeric types (timeout can be float for aiohttp, others should be int)
        timeout = float(timeout_override or self.config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
        retry_attempts = int(self.config.get(CONF_RETRY_ATTEMPTS, DEFAULT_RETRY_ATTEMPTS))
        retry_backoff = int(self.config.get(CONF_RETRY_BACKOFF, DEFAULT_RETRY_BACKOFF))

        # Render templates
        try:
            url = await self._render_template(url)
            headers = await self._render_headers(headers)
            payload = await self._render_payload(payload)
        except TemplateError as err:
            _LOGGER.error("Template rendering failed for webhook %s: %s", webhook_id, err)
            await self._fire_error_event(webhook_id, ERROR_TEMPLATE, str(err), 0)
            raise

        # Execute with retry logic
        last_error = None
        for attempt in range(retry_attempts):
            try:
                response_data = await self._make_request(
                    url=url,
                    method=method,
                    headers=headers,
                    payload=payload,
                    timeout=timeout,
                )

                # Success - fire success event
                self.hass.bus.async_fire(
                    EVENT_WEBHOOK_SUCCESS,
                    {
                        "webhook_id": webhook_id,
                        "status_code": response_data["status_code"],
                        "attempt": attempt + 1,
                    },
                )

                _LOGGER.debug(
                    "Webhook %s executed successfully on attempt %d: %s",
                    webhook_id,
                    attempt + 1,
                    response_data["status_code"],
                )

                return response_data

            except aiohttp.ClientConnectorError as err:
                last_error = (ERROR_CONNECTION, str(err))
                _LOGGER.warning(
                    "Connection error for webhook %s (attempt %d/%d): %s",
                    webhook_id,
                    attempt + 1,
                    retry_attempts,
                    err,
                )

            except asyncio.TimeoutError as err:
                last_error = (ERROR_TIMEOUT, str(err))
                _LOGGER.warning(
                    "Timeout for webhook %s (attempt %d/%d)",
                    webhook_id,
                    attempt + 1,
                    retry_attempts,
                )

            except aiohttp.ClientResponseError as err:
                last_error = (ERROR_HTTP, f"HTTP {err.status}: {err.message}")

                # Don't retry on 4xx errors (except 429 rate limit)
                if 400 <= err.status < 500 and err.status != 429:
                    _LOGGER.error(
                        "Non-retryable HTTP error for webhook %s: %s",
                        webhook_id,
                        last_error[1],
                    )
                    await self._fire_error_event(
                        webhook_id,
                        last_error[0],
                        last_error[1],
                        attempt + 1,
                        err.status,
                    )
                    raise

                _LOGGER.warning(
                    "HTTP error for webhook %s (attempt %d/%d): %s",
                    webhook_id,
                    attempt + 1,
                    retry_attempts,
                    last_error[1],
                )

            except Exception as err:
                last_error = (ERROR_CONNECTION, str(err))
                _LOGGER.error(
                    "Unexpected error for webhook %s (attempt %d/%d): %s",
                    webhook_id,
                    attempt + 1,
                    retry_attempts,
                    err,
                )

            # Wait before retry (exponential backoff)
            if attempt < retry_attempts - 1:
                wait_time = int(retry_backoff ** attempt)
                _LOGGER.debug(
                    "Waiting %d seconds before retry %d for webhook %s",
                    wait_time,
                    attempt + 2,
                    webhook_id,
                )
                await asyncio.sleep(wait_time)

        # All retries exhausted
        if last_error:
            error_type, error_message = last_error
            await self._fire_error_event(
                webhook_id,
                error_type,
                error_message,
                retry_attempts,
            )
            raise HomeAssistantError(f"Webhook {webhook_id} failed after {retry_attempts} attempts: {error_message}")

    async def _make_request(
        self,
        url: str,
        method: str,
        headers: dict[str, str],
        payload: Any,
        timeout: int | float,
    ) -> dict[str, Any]:
        """Make HTTP request and return response data."""
        request_kwargs = {
            "headers": headers,
            "timeout": aiohttp.ClientTimeout(total=timeout),
        }

        # Add payload for methods that support body
        if method.upper() in ["POST", "PUT", "PATCH"] and payload is not None:
            if isinstance(payload, (dict, list)):
                request_kwargs["json"] = payload
            else:
                request_kwargs["data"] = str(payload)

        _LOGGER.debug("Making %s request to %s", method, url)

        async with self.session.request(method, url, **request_kwargs) as response:
            # Raise for 4xx and 5xx status codes
            response.raise_for_status()

            # Check response size from headers
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_RESPONSE_SIZE:
                        raise HomeAssistantError(
                            f"Response size ({content_length} bytes) exceeds maximum allowed ({MAX_RESPONSE_SIZE} bytes)"
                        )
                except ValueError:
                    pass  # Invalid Content-Length header, continue anyway

            # Parse response - get text first with size limit
            response_text = await response.text()

            # Check actual size after reading and truncate if needed
            response_bytes = response_text.encode('utf-8')
            if len(response_bytes) > MAX_RESPONSE_SIZE:
                _LOGGER.warning(
                    "Response size (%d bytes) exceeds limit, truncating to %d bytes",
                    len(response_bytes),
                    MAX_RESPONSE_SIZE
                )
                # Truncate to max size in bytes, then decode
                response_text = response_bytes[:MAX_RESPONSE_SIZE].decode('utf-8', errors='ignore')

            response_json = None

            # Try to parse JSON from text
            if response_text:
                try:
                    response_json = json.loads(response_text)
                except json.JSONDecodeError:
                    pass

            return {
                "status_code": response.status,
                "headers": dict(response.headers),
                "body": response_text,
                "json": response_json,
            }

    async def _render_template(self, value: Any) -> str | Any:
        """Render a template value."""
        if not isinstance(value, str):
            return value

        if "{{" in value or "{%" in value:
            template = Template(value, self.hass)
            return template.async_render()

        return value

    async def _render_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Render all header values."""
        rendered: dict[str, str] = {}
        for key, value in headers.items():
            rendered[key] = str(await self._render_template(value))
        return rendered

    async def _render_payload(self, payload: Any) -> Any:
        """Render payload with template support recursively."""
        if payload is None:
            return None

        # If payload is a string, try to render it
        if isinstance(payload, str):
            rendered = await self._render_template(payload)
            # Try to parse as JSON if it looks like JSON
            if rendered.strip().startswith(("{", "[")):
                try:
                    return json.loads(rendered)
                except json.JSONDecodeError:
                    pass
            return rendered

        # If payload is a dict, render each value recursively
        if isinstance(payload, dict):
            rendered = {}
            for key, value in payload.items():
                # Recursively render nested structures
                rendered[key] = await self._render_payload(value)
            return rendered

        # If payload is a list, render each item recursively
        if isinstance(payload, list):
            return [await self._render_payload(item) for item in payload]

        return payload

    async def _fire_error_event(
        self,
        webhook_id: str,
        error_type: str,
        error_message: str,
        attempt: int,
        status_code: int | None = None,
    ) -> None:
        """Fire error event for failed webhook."""
        event_data = {
            "webhook_id": webhook_id,
            "error_type": error_type,
            "error_message": error_message,
            "attempt": attempt,
        }

        if status_code:
            event_data["status_code"] = status_code

        self.hass.bus.async_fire(EVENT_WEBHOOK_ERROR, event_data)
