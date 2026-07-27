# Bowers & Wilkins Zeppelin — Home Assistant Integration

Custom [HACS](https://hacs.xyz/) integration for controlling B&W Formation/Zeppelin speakers over the local network.

Built by reverse-engineering the B&W Splice Android app. All communication is local — no cloud, no account required.

## Supported Devices

| Device | Type ID |
|---|---|
| Zeppelin Pro | `com.bowerswilkins.liberty.zpr` |
| Zeppelin | `com.bowerswilkins.liberty.zep` |
| Panorama 3 | `com.bowerswilkins.liberty.alb` |
| Formation Duo | `com.bowerswilkins.liberty.ps1` |
| Formation Flex | `com.bowerswilkins.liberty.st1` |
| Formation Bar | `com.bowerswilkins.liberty.sb1` |
| Formation Bass | `com.bowerswilkins.liberty.sw1` |
| Formation Audio | `com.bowerswilkins.liberty.connect` |

> Only tested on Zeppelin Pro. Other devices should work but are untested.

## Features

### LED Light Control

Exposed as a standard `light` entity with:
- On / Off
- RGB color picker (full 0-255 range per channel)
- Brightness slider (0-100%)

### Firmware Update Check

Checks for firmware updates once per night at a random time between 3:00 and 5:59 AM. If an update is available, a persistent notification is created in Home Assistant with the version number and release notes.

## How It Works

The integration communicates with the speaker over its local REST API on port **42425** (HTTPS with self-signed certificate). Devices are discovered via the speaker's mesh node list.

The protocol is a JSON-RPC-like system called "StateD", sent to:

```
POST /mesh/node/{nodeId}/channel/com.bowerswilkins.stated.service+provider/message
```

```json
{
  "type": "query",
  "method": {
    "name": "get_property",
    "parameters": {
      "property": "liberty.lights.hardware-downlight"
    }
  }
}
```

No polling — the integration fetches the LED state once on startup and tracks it locally after that.

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Install "Bowers & Wilkins Zeppelin"
3. Restart Home Assistant

### Manual

Copy `custom_components/bw_zeppelin` to your Home Assistant `custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Integrations → Add Integration**
2. Search for "Bowers & Wilkins Zeppelin"
3. Enter the speaker's IP address
4. The integration auto-discovers the speaker name and node ID

> Tip: assign a static IP or DHCP reservation to your speaker so the address doesn't change.

## Known Limitations

- The speaker uses a self-signed TLS certificate — SSL verification is disabled for local communication.
- The Splice app may not discover speakers connected via Ethernet. This integration works fine over Ethernet.
- Only LED control and firmware update checks are implemented. Volume, playback, and source control are possible via the same API but not yet exposed.

## API Reference

The speaker exposes more capabilities that could be added in the future:

| Feature | API |
|---|---|
| Volume | `set_volume` / `get_volume` (0-100) |
| EQ | `liberty.property.gain.treble` / `.bass` / `.offset` |
| Playback | `liberty.command.play_pause` / `next_track` / `previous_track` |
| Seek | `liberty.command.seek_absolute` / `seek_relative` (ms) |
| Source switch | `liberty.command.pull_source` |
| Now playing | `liberty.oobed.audiotile` |
| AUX input | `liberty.property.connect.analog.*` |
| Optical input | `liberty.property.connect.digital.*` |
| Bluetooth | `liberty.oobed.bluetooth.command.*` |
| Device info | `liberty.oobed.device_info` |
| Restart | `request_restart` |

Audio sources supported by the hardware: AirPlay 2, Spotify Connect, Roon, DLNA, Bluetooth, AUX, Optical, QPlay.

## License

MIT
