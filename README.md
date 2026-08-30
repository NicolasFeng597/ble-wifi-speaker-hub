# BLE/Wi-Fi Speaker Project
Wi-Fi speaker hub with a BLE remote, where the speaker connects via Wi-Fi to a MacBook while also serving a BLE
link to the remote.
Using a Nordic hardware stack and Zephyr firmware stack.

## Status
Obtained setup measurements mirroring Nordic's
[ble-coex sample](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/ble_coex/README.html):

(Wi-Fi 802.11n in 2.4GHz, separate antennas)
| Test Case | Wi-Fi UDP TX throughput in Mbps | Bluetooth LE throughput in kbps |
|---|---|---|
| Wi-Fi only, client (UDP TX) | 8.30 | N.A.|
| Bluetooth LE-only, central | N.A. | 1377 |
| Wi-Fi and Bluetooth LE, coexistence disabled | 7.46 | 498 |
| Wi-Fi and Bluetooth LE, coexistence enabled | 6.47 | 634 |

See `docs/notes.md` for additional info.

## Hardware
| Device | Role |
|---|---|
| nRF7002 DK | BLE peripheral/GATT server, WiFi client with MacBook server |
| nRF5340 DK | BLE central/GATT client |
| nRF52840 Dongle | BLE sniffer |
| MacBook | Wi-Fi server |

## Notes
`docs/notes.md`