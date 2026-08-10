# BLE/Wi-Fi Speaker Project

Communications-focused Wi-Fi speaker hub with a BLE remote, where the speaker connects via Wi-Fi to a MacBook while also serving a BLE
link to the remote.
Using a Nordic hardware stack and Zephyr firmware stack.

## Status
Initial hardware config and packet sniffing done, compared setup measurements with Nordic's
[ble-coex sample](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/ble_coex/README.html)
(see `docs/notes.md`).

## Hardware
| Device | Role |
|---|---|
| nRF7002 DK | BLE peripheral/GATT server, WiFi client with MacBook server |
| nRF5340 DK | BLE central/GATT client |
| nRF52840 Dongle | BLE sniffer |
| MacBook | Wi-Fi server |

## Notes
`docs/notes.md`