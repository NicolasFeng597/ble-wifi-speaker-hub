# BLE/Wi-Fi Speaker Project
Wi-Fi speaker hub with a BLE remote, where the speaker connects via Wi-Fi to a MacBook while also serving a BLE
link to the remote.
Using a Nordic hardware stack and Zephyr firmware stack.

## Status
Obtained existing nRF 700x arbitration policy differences on local setup:

(Wi-Fi 802.11n in 2.4GHz, separate antennas)
| Test Case | Wi-Fi UDP TX throughput in Mbps | Bluetooth LE throughput in kbps |
|---|---|---|
| Wi-Fi only, client (UDP TX) | 8.30 | N.A.|
| Bluetooth LE-only, central | N.A. | 1377 |
| Wi-Fi and Bluetooth LE, coexistence disabled | 7.46 | 498 |
| Wi-Fi and Bluetooth LE, coexistence enabled | 6.47 | 634 |

Generally, arbitration radio grants are < 10 ms, however outliers take up 30% of all runtime (due to missed link layer connection interval events). Currently working on a policy to help with this right skew.

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