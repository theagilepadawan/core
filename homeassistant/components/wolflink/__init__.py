"""The Wolf SmartSet Service integration."""
from datetime import timedelta
import logging

from httpcore import ConnectError, ConnectTimeout
from wolf_smartset.token_auth import InvalidAuth
from wolf_smartset.wolf_client import WolfClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COORDINATOR,
    DEVICE_GATEWAY,
    DEVICE_ID,
    DEVICE_NAME,
    DOMAIN,
    PARAMETERS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Wolf SmartSet Service component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Wolf SmartSet Service from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    device_name = entry.data[DEVICE_NAME]
    device_id = entry.data[DEVICE_ID]
    gateway_id = entry.data[DEVICE_GATEWAY]
    _LOGGER.debug(
        "Setting up wolflink integration for device: %s (id: %s, gateway: %s)",
        device_name,
        device_id,
        gateway_id,
    )

    wolf_client = WolfClient(username, password)

    parameters = await fetch_parameters(wolf_client, gateway_id, device_id)

    async def async_update_data():
        """Update all stored entities for Wolf SmartSet."""
        try:
            values = await wolf_client.fetch_value(gateway_id, device_id, parameters)
            return {v.value_id: v.value for v in values}
        except ConnectError as exception:
            raise UpdateFailed(
                f"Error communicating with API: {exception}"
            ) from exception
        except InvalidAuth as exception:
            raise UpdateFailed("Invalid authentication during update.") from exception

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="wolflink",
        update_method=async_update_data,
        update_interval=timedelta(minutes=1),
    )

    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id][PARAMETERS] = parameters
    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator
    hass.data[DOMAIN][entry.entry_id][DEVICE_ID] = device_id

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def fetch_parameters(client: WolfClient, gateway_id: int, device_id: int):
    """
    Fetch all available parameters with usage of WolfClient.

    By default Reglertyp entity is removed because API will not provide value for this parameter.
    """
    try:
        fetched_parameters = await client.fetch_parameters(gateway_id, device_id)
        return [param for param in fetched_parameters if param.name != "Reglertyp"]
    except (ConnectError, ConnectTimeout) as exception:
        raise UpdateFailed(f"Error communicating with API: {exception}") from exception
    except InvalidAuth as exception:
        raise UpdateFailed("Invalid authentication during update") from exception
