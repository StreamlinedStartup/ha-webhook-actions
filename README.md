# Webhook Actions

Send HTTP requests from Home Assistant automations. Use templates to insert real-time data.

## Requirements

- Home Assistant 2023.7.0 or newer
- Network access to webhook endpoints

## Installation

1. Download latest release from GitHub
2. Extract files
3. Copy `custom_components/webhook_actions` folder to your Home Assistant `config/custom_components/` directory
4. Restart Home Assistant
5. Go to Settings → Devices & Services
6. Click Add Integration
7. Search for "Webhook Actions"

## Setup

### Add Webhook

**Settings → Devices & Services → Add Integration → Webhook Actions**

Required fields:
- **Webhook ID**: Unique name (example: `discord_alert`)
- **Name**: Display name
- **URL**: Target endpoint

Optional fields:
- **Method**: GET, POST, PUT, PATCH, DELETE (default: POST)
- **Headers**: JSON object
- **Payload**: JSON object or string
- **Timeout**: Seconds (default: 10)
- **Retry Attempts**: Number of retries (default: 3)

### Example Setup

```
Webhook ID: notify_discord
Name: Discord Notifications
URL: https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
Method: POST
Headers: {"Content-Type": "application/json"}
Payload: {"content": "Alert from Home Assistant"}
```

## Usage

### Basic Call

```yaml
service: webhook_actions.call
data:
  webhook_id: notify_discord
```

### With Templates

```yaml
service: webhook_actions.call
data:
  webhook_id: notify_discord
  payload_override:
    content: "Temperature: {{ states('sensor.living_room_temp') }}°C"
```

### In Automations

```yaml
automation:
  - alias: Door Alert
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: webhook_actions.call
        data:
          webhook_id: notify_discord
          payload_override:
            content: "Front door opened at {{ now().strftime('%H:%M') }}"
```

## Templates

Use `{{ }}` to insert live data.

### Entity States

```yaml
payload_override:
  temperature: "{{ states('sensor.temperature') }}"
  humidity: "{{ states('sensor.humidity') }}"
```

### Time and Date

```yaml
payload_override:
  timestamp: "{{ now().isoformat() }}"
  time: "{{ now().strftime('%H:%M:%S') }}"
  date: "{{ now().strftime('%Y-%m-%d') }}"
```

### Conditions

```yaml
payload_override:
  status: >
    {% if states('sensor.temperature') | float > 25 %}
      Hot
    {% else %}
      Normal
    {% endif %}
```

### Nested Data

```yaml
payload_override:
  location: home
  sensors:
    temperature: "{{ states('sensor.temp') }}"
    humidity: "{{ states('sensor.humidity') }}"
  metadata:
    timestamp: "{{ now().isoformat() }}"
```

## Response Data

Capture webhook responses:

```yaml
action:
  - service: webhook_actions.call
    data:
      webhook_id: api_check
    response_variable: api_response

  - condition: template
    value_template: "{{ api_response.status_code == 200 }}"

  - service: notify.mobile_app
    data:
      message: "API returned: {{ api_response.json.data }}"
```

Response contains:
- `status_code`: HTTP status (200, 404, etc)
- `headers`: Response headers
- `body`: Raw response text
- `json`: Parsed JSON (if applicable)

## Override Parameters

Change webhook settings per call:

```yaml
service: webhook_actions.call
data:
  webhook_id: my_webhook
  url_override: "https://api.example.com/v2/endpoint"
  headers_override:
    Authorization: "Bearer {{ states('input_text.api_token') }}"
  payload_override:
    data: "Custom payload"
  timeout: 30
```

## Error Handling

### Listen for Failures

```yaml
automation:
  - alias: Webhook Error Handler
    trigger:
      - platform: event
        event_type: webhook_actions_error
    action:
      - service: persistent_notification.create
        data:
          title: Webhook Failed
          message: >
            Webhook: {{ trigger.event.data.webhook_id }}
            Error: {{ trigger.event.data.error_message }}
```

### Listen for Success

```yaml
automation:
  - alias: Webhook Success Logger
    trigger:
      - platform: event
        event_type: webhook_actions_success
    action:
      - service: logbook.log
        data:
          name: Webhook Success
          message: "{{ trigger.event.data.webhook_id }} completed"
```

## Common Use Cases

### Discord Notifications

```yaml
service: webhook_actions.call
data:
  webhook_id: discord
  payload_override:
    username: Home Assistant
    content: "{{ message }}"
    embeds:
      - title: "{{ title }}"
        description: "{{ description }}"
        color: 3447003
```

### Slack Messages

```yaml
service: webhook_actions.call
data:
  webhook_id: slack
  payload_override:
    text: "Temperature Alert"
    blocks:
      - type: section
        text:
          type: mrkdwn
          text: "Current temp: {{ states('sensor.temp') }}°C"
```

### IFTTT Trigger

```yaml
service: webhook_actions.call
data:
  webhook_id: ifttt
  payload_override:
    value1: "{{ trigger.to_state.state }}"
    value2: "{{ now().isoformat() }}"
```

### n8n Workflow

```yaml
service: webhook_actions.call
data:
  webhook_id: n8n
  payload_override:
    event: door_opened
    location: "{{ area_name(trigger.entity_id) }}"
    timestamp: "{{ now().timestamp() }}"
```

## Troubleshooting

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.webhook_actions: debug
```

Restart Home Assistant. Check logs: **Settings → System → Logs**

### Common Issues

**Integration won't load**
- Restart Home Assistant
- Check logs for errors
- Verify all files copied correctly

**Templates not working**
- Test in Developer Tools → Template
- Check entity IDs are correct
- Ensure quotes around template strings

**Connection errors**
- Verify URL is correct
- Check network connectivity
- Confirm endpoint is accessible from HA

**Timeout errors**
- Increase timeout value
- Check webhook endpoint response time
- Verify network stability

## Configuration

### YAML Configuration

Add to `configuration.yaml`:

```yaml
webhook_actions:
  webhooks:
    - webhook_id: example
      name: Example Webhook
      url: https://example.com/webhook
      method: POST
      headers:
        Content-Type: application/json
      timeout: 15
      retry_attempts: 3
```

### Multiple Webhooks

```yaml
webhook_actions:
  webhooks:
    - webhook_id: discord
      name: Discord
      url: https://discord.com/api/webhooks/ID/TOKEN
      method: POST

    - webhook_id: slack
      name: Slack
      url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
      method: POST

    - webhook_id: custom_api
      name: Custom API
      url: https://api.example.com/endpoint
      method: POST
      headers:
        Authorization: Bearer YOUR_TOKEN
```

## Limits

- Maximum response size: 1 MB
- Default timeout: 10 seconds
- Maximum timeout: 300 seconds (5 minutes)
- Default retries: 3 attempts
- Maximum retries: 10 attempts

## Security

- Store sensitive tokens in Home Assistant secrets
- Use HTTPS endpoints when possible
- Validate webhook URLs before adding
- Review logs for unauthorized access attempts

### Using Secrets

In `secrets.yaml`:
```yaml
discord_webhook: https://discord.com/api/webhooks/ID/TOKEN
api_token: your_secret_token
```

In automation:
```yaml
service: webhook_actions.call
data:
  webhook_id: secure_webhook
  url_override: !secret discord_webhook
  headers_override:
    Authorization: !secret api_token
```

## Support

- Issues: https://github.com/StreamlinedStartup/ha-webhook-actions/issues
- Discussions: https://github.com/StreamlinedStartup/ha-webhook-actions/discussions

## License

MIT License
