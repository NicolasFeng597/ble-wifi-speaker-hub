**7/26**
- set up nrfconnect/dev env, started sdk and ble fundamentals
- looked through blinky code and devicetrees

**8/2**
- got nrf5340 and nrf7002 working for uart peripheral/central setup
- sniffed gap packets with nrf52840 on wireshark
- pushed repo
- bug with nrf7002 ns peripheral build, use non-ns build

**8/8 and 8/9**
- duplicating Nordic's [ble_coex sample](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/ble_coex/README.html) with my setup
- using the 5 GHz band instead of the RJ45 wifi connection, since the testing is on the 2.4 GHz band
- iperf version 2.2.1
- nrf7002: 1050762608
- nrf5340: 1050061183

reference data, Wi-Fi 802.11n in 2.4 GHz, separate antennas
| Test Case | Wi-Fi UDP TX throughput in Mbps | Bluetooth LE throughput in kbps |
|---|---|---|
| Wi-Fi only, client (UDP TX) | 10.2 | N.A.|
| Bluetooth LE-only, central | N.A. | 1107 |
| Wi-Fi and Bluetooth LE, coexistence disabled | 9.9 | 145 |
| Wi-Fi and Bluetooth LE, coexistence enabled | 8.3 | 478 |

collected data, Wi-Fi 802.11n in 2.4 GHz, separate antennas
| Test Case | Wi-Fi UDP TX throughput in Mbps | Bluetooth LE throughput in kbps |
|---|---|---|
| Wi-Fi only, client (UDP TX) | 8.64 | N.A.|
| Bluetooth LE-only, central | N.A. | 1359 |
| Wi-Fi and Bluetooth LE, coexistence disabled | 7.62 | 325 |
| Wi-Fi and Bluetooth LE, coexistence enabled | 6.51 | 553 |