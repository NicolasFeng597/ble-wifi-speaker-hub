**7/26**
- set up nrfconnect/dev env, started sdk and ble fundamentals
- looked through blinky code and devicetrees

**8/2**
- got nrf5340 and nrf7002 working for uart peripheral/central setup (removed by 10/26, see initial commit)
- sniffed gap packets with nrf52840 on wireshark
- pushed repo
- bug with nrf7002 ns peripheral build, use non-ns build

**8/8 and 8/9**
- duplicating Nordic's [ble_coex sample](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/ble_coex/README.html)
with my setup
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
| Wi-Fi only, client (UDP TX) | 8.30 | N.A.|
| Bluetooth LE-only, central | N.A. | 1377 |
| Wi-Fi and Bluetooth LE, coexistence disabled | 7.46 | 498 |
| Wi-Fi and Bluetooth LE, coexistence enabled | 6.47 | 634 |

**8/28 to 9/1**
- measuring latency for connectional intervals without coex
- added logging for bt_throughput_write(), but that only has delay for a TX write-no-read buffer,
which is indirectly what I want to see
- edited the mpsl_cx_nrf700x coex driver code, printing the delay between a PTA request() and its
corresponding grant high signal (~5 ms delay between direct request()/grant() calls and
bt_throughput_write() latency)
- k_uptime_get_32() uses a spinlock that doesn't meet request() timing constraints since it's called
"shortly before radio operations", must use k_cycle_get_32()
- the coex code is on the net core so logging is through VCOM0 instead of VCOM1
- Ran logging, 99.4% of 13496 requests are < 10 ms, otherwise 12.5s of 35s period was taken up by requests > 10 ms

**10/17 to 10/28**
- found that majority of request() calls (multiple per connection event) have low priority, ~0.04% have high priority (see data for specific time stamps)
- explored setting the request wire between first request and last grant instead of turning it on and off between denied grants, however this would fail if it was granted after the connection interval, granting Tx to an asleep BLE controller for a worse-case 99 ms with 100 ms connection interval (assuming minimal connection interval request retries)
- for UDP, sending an earlier request signal before connection events could increase odds of getting radio access, also avoiding the above case by the default of setting request low during regular request calls. MPSL's mpsl_radio_notification_cfg_set() has a callback that runs 200-5500 us before these events, so we can set the request wire there.