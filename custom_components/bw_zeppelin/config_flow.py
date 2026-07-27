from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_client import BwZeppelinApiClient, BwZeppelinApiError
from .const import CONF_FW_VERSION, CONF_HOST, CONF_MODEL, CONF_NODE_ID, CONF_SPACE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class BwZeppelinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            session = async_get_clientsession(self.hass, verify_ssl=False)
            client = BwZeppelinApiClient(session=session, host=host)
            try:
                fw_version = await client.get_version()
                nodes = await client.get_nodes()
            except BwZeppelinApiError:
                errors["base"] = "cannot_connect"
            else:
                if not nodes:
                    errors["base"] = "no_devices"
                else:
                    node = nodes[0]
                    node_id = node["nodeID"]
                    space_name = node.get("space-name", "Zeppelin")
                    model = node.get("type", "unknown")

                    await self.async_set_unique_id(node_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=space_name,
                        data={
                            CONF_HOST: host,
                            CONF_NODE_ID: node_id,
                            CONF_SPACE_NAME: space_name,
                            CONF_MODEL: model,
                            CONF_FW_VERSION: fw_version,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
