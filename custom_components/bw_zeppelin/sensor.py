from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_FW_VERSION, CONF_MODEL, CONF_NODE_ID, CONF_SPACE_NAME, DOMAIN
from .light import DEVICE_TYPE_NAMES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    device_info_data = data.get("device_info", {})
    node_id = entry.data[CONF_NODE_ID]
    model_type = entry.data.get(CONF_MODEL, "unknown")

    device_info = {
        "identifiers": {(DOMAIN, node_id)},
        "name": entry.data.get(CONF_SPACE_NAME, "Zeppelin"),
        "manufacturer": "Bowers & Wilkins",
        "model": DEVICE_TYPE_NAMES.get(model_type, model_type),
        "sw_version": entry.data.get(CONF_FW_VERSION),
    }

    sensors = [
        BwZeppelinDiagnosticSensor(
            node_id, device_info, "Firmware Version",
            entry.data.get(CONF_FW_VERSION, "unknown"), "mdi:chip",
        ),
        BwZeppelinDiagnosticSensor(
            node_id, device_info, "Serial Number",
            device_info_data.get("SerialNumber", "unknown"), "mdi:identifier",
        ),
        BwZeppelinDiagnosticSensor(
            node_id, device_info, "Model",
            device_info_data.get("ModelNumber", "unknown"), "mdi:speaker",
        ),
        BwZeppelinDiagnosticSensor(
            node_id, device_info, "Bluetooth MAC",
            _format_mac(device_info_data.get("BTMacAddress", "")), "mdi:bluetooth",
        ),
    ]
    async_add_entities(sensors)


def _format_mac(raw: str) -> str:
    if len(raw) == 12:
        return ":".join(raw[i:i+2].upper() for i in range(0, 12, 2))
    return raw or "unknown"


class BwZeppelinDiagnosticSensor(SensorEntity):

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        node_id: str,
        device_info: dict,
        name: str,
        value: str,
        icon: str,
    ) -> None:
        self._attr_name = name
        self._attr_native_value = value
        self._attr_icon = icon
        self._attr_unique_id = f"{node_id}_{name.lower().replace(' ', '_')}"
        self._attr_device_info = device_info
