# Hardy Barth eCB1

Home Assistant custom integration for reading Hardy Barth eCB1 data from the
local HTTP API.

## Installation

Copy `custom_components/ha_hardy_barth_ecb1` into the `custom_components`
directory of your Home Assistant configuration, restart Home Assistant, and
add **Hardy Barth eCB1** from Settings > Devices & services.

Enter the hostname or IP address of the eCB1 when prompted. The integration
currently reads the `/api/v1/all` endpoint and creates sensors for meter power,
total imported energy, charging state, and requested charging current when
those values are returned by the device.

## Development

Install the development requirements and run the lint script from the
repository root:

```text
pip install -r requirements_dev.txt
scripts\lint
```
