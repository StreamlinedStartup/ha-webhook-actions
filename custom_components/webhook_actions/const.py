"""Constants for the Webhook Actions integration."""

DOMAIN = "webhook_actions"

# Configuration keys
CONF_WEBHOOKS = "webhooks"
CONF_WEBHOOK_ID = "webhook_id"
CONF_NAME = "name"
CONF_URL = "url"
CONF_METHOD = "method"
CONF_HEADERS = "headers"
CONF_PAYLOAD = "payload"
CONF_TIMEOUT = "timeout"
CONF_RETRY_ATTEMPTS = "retry_attempts"
CONF_RETRY_BACKOFF = "retry_backoff"

# Service call overrides
CONF_URL_OVERRIDE = "url_override"
CONF_HEADERS_OVERRIDE = "headers_override"
CONF_PAYLOAD_OVERRIDE = "payload_override"
CONF_TIMEOUT_OVERRIDE = "timeout"

# HTTP methods
HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

# Default values
DEFAULT_METHOD = "POST"
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 2
DEFAULT_HEADERS = {"Content-Type": "application/json"}
MAX_RESPONSE_SIZE = 1024 * 1024  # 1MB max response size

# Service names
SERVICE_CALL = "call"

# Event types
EVENT_WEBHOOK_ERROR = f"{DOMAIN}_error"
EVENT_WEBHOOK_SUCCESS = f"{DOMAIN}_success"

# Error types
ERROR_CONNECTION = "connection_error"
ERROR_TIMEOUT = "timeout_error"
ERROR_HTTP = "http_error"
ERROR_TEMPLATE = "template_error"
ERROR_INVALID_CONFIG = "invalid_config"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"
