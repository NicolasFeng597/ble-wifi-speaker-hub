# BLE/Wi-Fi Speaker Project

Communications-focused Wi-Fi speaker hub with a BLE remote, where the speaker connects via Wi-Fi to a MacBook while also serving a BLE
link to the remote.
Using a Nordic hardware stack and Zephyr firmware stack.

## Status
Initial hardware config and packet sniffing done, looking into packet/protocol format and coexistence.

## Hardware
| Device | Role |
|---|---|
| nRF7002 DK | BLE peripheral/GATT server, WiFi client with MacBook server |
| nRF5340 DK | BLE central/GATT client |
| nRF52840 Dongle | BLE sniffer |
| MacBook | Wi-Fi server |

## Notes
`docs/notes.md`