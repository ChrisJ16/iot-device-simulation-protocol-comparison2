# iot-device-simulation-protocol-comparison2

This repository simulates a small-scale IoT system with devices speaking MQTT, CoAP and Modbus/TCP. It focuses on
protocol comparison, fault-injection (loss / latency / temporary device failures), and simple experiment runs with
CSV-based logging and a lightweight live visualiser.

Overview
--------

- Simulated protocols: MQTT (publish), CoAP (client/server), Modbus/TCP (server + poller).
- Gateway/poller components normalise all incoming records into a single CSV format so the visualiser and experiments
  can operate on a common dataset.
- Fault injection: configurable packet loss, added latency and temporary device failure; these are controlled via
  `config.json` and propagated into the runtime `faults` module on startup.

Quick start (WSL, or Linux enviroment)
------------------------

1. Create & activate a venv:

```bash
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. (Optional but recommended) Run an MQTT broker such as Mosquitto. On Linux:

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
mosquitto -d
```

The demo will attempt to start an embedded broker if a system broker is not available, but using a system broker is more reliable.

4. Start the simulation:

```powershell
python run_demo.py
```

The script reinitialises the output CSV files on startup and runs until interrupted (Ctrl+C).

Key files produced
------------------

- `all_devices_recorded_data.csv`  unified collector output. Header: `device_id,time,date,protocol,sensor_type,value,send_ts,receive_ts,latency_ms`.
- `sent_messages.csv`  log of attempted sends (used to compute PDR per device).
- `experiments_results.csv`  summary output when using `experiments.py` to run parameter sweeps.

Configuration (`config.json`)
-----------------------------

Relevant keys:

- `path_to_data_file` (default: `data/data.txt`)
- `rows_to_read` (initial parser)
- `num_devices_mqtt`, `num_devices_coap`, `num_devices_modbus`
- `message_interval_mqtt` (`-1` = random interval)
- `mqtt_broker`, `mqtt_topic`

Fault-injection keys:

- `loss_rate`: float 0.0-1.0 (probability to drop outgoing message)
- `latency_range`: `[min_ms, max_ms]` (added random delay in milliseconds)
- `fail_prob`: float (probability a device enters temporary failed state)

Example `config.json` snippet:

```json
{
  "rows_to_read": 1000,
  "path_to_data_file": "data/data.txt",
  "num_devices_mqtt": 6,
  "num_devices_coap": 2,
  "num_devices_modbus": 2,
  "message_interval_mqtt": 4,
  "mqtt_broker": "localhost",
  "mqtt_topic": "iot",
  "loss_rate": 0.1,
  "latency_range": [100, 500],
  "fail_prob": 0.02
}
```

How it works (summary)
----------------------

- `run_demo.py` parses initial sample data into `parsed_data_*` CSVs, starts a local/embedded MQTT broker and a collector,
  spawns simulated devices and starts Modbus/CoAP components as configured.
- Devices include `send_ts` in payloads; collectors record `receive_ts` and compute `latency_ms` where possible. The
  Modbus poller and CoAP server normalise responses into the same CSV schema.
- `run_demo.py` now propagates the `loss_rate`, `latency_range` and `fail_prob` values into the `faults` module at
  startup so they are available to devices and pollers.

Visualiser
----------

Open `visualiser.ipynb` and run the `live_dashboard()` cell. The notebook shows:

- Time-series plots for `light`, `humidity` and `temperature` (last N points per device).
- Right-side metrics: Packet Delivery Ratio (PDR) per device, average latency per device, and records-per-protocol.

PDR is computed using `sent_messages.csv` (attempted sends) and `all_devices_recorded_data.csv` (received records). The
notebook includes heuristics to compute `latency_ms` from `send_ts` and `receive_ts` if the latency column is missing.

Running experiments
-------------------

Run `experiments.py` to perform automated parameter sweeps across `loss_rate` and `fail_prob` values. The script runs
short simulations, collects per-run metrics and writes a summary to `experiments_results.csv`.

Interpreting results and expected protocol behaviour under stress
-----------------------------------------------------------------

The simulation is intentionally simple and does not fully implement some protocol reliability mechanisms (for example
MQTT QoS 1/2 retransmissions or CoAP confirmable messages) unless those are explicitly added in the device code. Use
these guidelines when interpreting results produced by this demo:

- Packet Delivery Ratio (PDR):
  - PDR is `received / sent` per device. When `loss_rate` is > 0, expect PDR to drop for push-based protocols that don't
    implement retransmission (MQTT default QoS=0 in this demo, CoAP non-confirmable by default).
  - Polling protocols (Modbus) may show higher stability under transient loss because the poller retries at the next
    scheduled poll; however, repeated failures reduce the recorded rate.

- Latency:
  - Increasing `latency_range` increases observed `avg_latency_ms` values. If delays exceed device send intervals, data
    can appear bursty or arrive late relative to send timestamps.

- Device failures:
  - Raising `fail_prob` creates gaps in time-series plots and reduces PDR for affected devices.

Protocol comparison notes (what to look for):

- MQTT (push): tends to be sensitive to packet loss if QoS is 0  expect lower PDR at higher `loss_rate`.
- CoAP (push-like): behavior depends on whether confirmable messages/retransmissions are implemented; with non-confirmable
  messages it behaves like UDP and is loss-sensitive.
- Modbus (polling): more deterministic records while polls succeed; under loss the poller may see repeated failures but the
  overall delivery pattern is periodic when healthy.

Results
-------

- This simulation simplifies many real-world aspects. If you need to evaluate protocol features like retransmission,
  acknowledgement, or ordered delivery you should extend the device/gateway implementations to explicitly model those features
- Concurrent CSV writes can sometimes leave partially written rows. The visualiser includes repair heuristics but if you
  see persistent corruption stop the demo and inspect the CSV files.

Practical checklist to observe faults & latency in the visualiser
----------------------------------------------------------------

1. Set `loss_rate` > 0 and `latency_range` to a non-zero window in `config.json`.
2. Restart `run_demo.py` so the `faults` module picks up the values.
3. Confirm `sent_messages.csv` is being appended to on every attempted send (this file is used to compute PDR).
4. Open `visualiser.ipynb` and run `live_dashboard()`  PDR and average latency panels should show deviations from ideal
   values as faults are exercised.

If PDR remains 1.0 even with `loss_rate` > 0 then either:

- `sent_messages.csv` is not being logged for attempted (but dropped) sends  the send path must call `storage.log_sent()`
  before checking `should_drop()`; or
- the code that evaluates `should_drop()` is not being executed for the protocol in question. If you want, I can
  instrument the send paths (`devices/*.py`, `gateway_modbus_poller.py`) to ensure attempted sends are always logged and
  that drops/delays are visible.

Files and purpose (summary)
--------------------------

- `run_demo.py`  orchestrator.
- `collector/mqtt_collector.py`  paho-mqtt based collector (subscribes to topic and saves messages).
- `collector/local_broker.py`  wrapper that attempts to start an embedded broker (`hbmqtt`) and falls back to system `mosquitto` if available.
- `devices/mqtt_device.py`  MQTT device thread implementation (publishes JSON to broker/topic).
- `storage.py`  thread-safe CSV storage helper; writes to `all_devices_recorded_data.csv` by default.
- `parsed_data_*.csv`  generated from the raw data source; used by devices to pick readings.
- `all_devices_recorded_data.csv`  collected messages recorded by the collector.
