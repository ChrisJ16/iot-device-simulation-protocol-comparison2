# iot-device-simulation-protocol-comparison

This repository offers an application which simulates a small-scale IoT system that connects multiple devices to a central collector using MQTT. The goal is to explore MQTT behavior, analyze scalability, and visualize system behavior. This repo showcases IoT basics: device simulation, protocol layers, data storage, and visualization.

## How to run (RECOMMENDED: Linux environment, WSL on Windows)

1. Create a virtual environment and activate it (optional but recommended; can use conda for easier environment management):

```bash
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Mosquitto (MQTT broker):

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
# start as daemon
mosquitto -d
# (or) systemd: sudo systemctl enable --now mosquitto
```

It's recommended to have a broker like Mosquitto available. The demo will attempt to start a local embedded broker if Mosquitto isn't present.

4. Unzip the archive located in **data/**

- Data source: [Intel Lab Data](https://db.csail.mit.edu/labdata/labdata.html)

5. Run the demo:

```bash
python run_demo.py
```

Stop the demo with Ctrl+C. Collected messages are appended to `all_devices_recorded_data.csv`.


## Configuration

The project is configured via `config.json` in the repository root. Key fields:

- `rows_to_read` — how many rows to parse from the raw data source when preparing the parsed CSVs (minimum 100 enforced by the parser).
- `path_to_data_file` — path to the raw data file used by the initial parser (default in repo: `data/data.txt`).
- `num_devices_mqtt` — number of simulated MQTT devices.
- `message_interval_mqtt` — per-device message interval in seconds. If set to `-1` each device chooses a random interval between 4–10s.
- `mqtt_broker` — broker host (defaults to `localhost`).
- `mqtt_topic` — topic used by MQTT devices and the collector.

Example:

```json
{
	"rows_to_read": 1000,
	"path_to_data_file": "data/data.txt",
	"num_devices_http": 7,
	"num_devices_mqtt": 8,
	"message_interval_http": 5,
	"message_interval_mqtt": 4,
	"protocol": "HTTP",
	"mqtt_broker": "localhost",
	"mqtt_topic": "iot",
	"http_server": ""
}
```

## How it works

- `run_demo.py` reads `config.json`, runs the initial data parser (this creates three parsed CSVs: `parsed_data_humidity_sensors.csv`, `parsed_data_light_sensors.csv`, and `parsed_data_temperature_sensors.csv`).
The script starts a local MQTT broker (if available) and an MQTT collector that subscribes to a topic, then spawns `num_devices_mqtt` devices that publish sensor readings to that topic.
- Devices pick a random sensor reading from the corresponding `parsed_data_*` CSVs and send it as JSON with the shape:

```json
{
	"device_id": "id_device3",
	"time": "12:34:56",
	"date": "2004-02-28",
	"protocol": "MQTT",
	"sensor_type": "temperature",
	"value": "23.45"
}
```

The collector saves received messages into a CSV file (`all_devices_recorded_data.csv`) with header `device_id,time,date,protocol,sensor_type,value,send_ts,receive_ts,latency_ms`.

## Visualizing results

The repository includes a Jupyter notebook `visualiser.ipynb` that you can use as a lightweight live dashboard:

1. Start `run_demo.py` in one terminal so data is being generated.
2. Open `visualiser.ipynb` in VS Code or Jupyter and run the cells. Call `live_dashboard()` to start a live refresh (plots update every 10s).

The notebook will automatically pick the appropriate CSV depending on `protocol` in `config.json` and plot three time-series charts (light, humidity, temperature), one line per device (up to the `num_devices_*` configured devices). Each device shows up to the last 20 points.

If you prefer a static snapshot, run the plotting cells once and export the figures to PNG via the notebook UI.

## Files and purpose

- `run_demo.py` — main orchestrator (parsing, starting collector and devices, graceful shutdown).
- `collector/mqtt_collector.py` — paho-mqtt based collector (subscribes to topic and saves messages).
- `collector/local_broker.py` — wrapper that attempts to start an embedded broker (`hbmqtt`) and falls back to system `mosquitto` if available.
- `devices/mqtt_device.py` — MQTT device thread implementation (publishes JSON to broker/topic).
- `storage.py` — thread-safe CSV storage helper; writes to `all_devices_recorded_data.csv` by default.
- `parsed_data_*.csv` — generated from the raw data source; used by devices to pick readings.
- `all_devices_recorded_data.csv` — collected messages recorded by the collector.

## Troubleshooting

- ImportError / hbmqtt websockets errors: `hbmqtt` is older and can conflict with modern `websockets`. The recommended flow is to install Mosquitto (system broker) and let `LocalBroker` detect it.
## Architecture

- Publish-Subscribe Pattern: MQTT devices
- Request-Response Pattern: (not used)
- Whole application: mixed, mainly Extract, Transform, Load (ETL) Pattern
