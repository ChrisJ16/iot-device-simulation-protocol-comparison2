import csv
import random
from pathlib import Path
import json
import threading
import time
import signal
import sys
from datetime import datetime

from collector.mqtt_collector import MqttCollector
from collector.local_broker import LocalBroker
from devices.mqtt_device import start_mqtt_device_thread
from storage import set_output_file
from storage import initialize_output, initialize_sent_log
import faults
from devices.modbus_device import start_modbus_device_thread
from gateway_modbus_poller import ModbusPoller
from gateway_coap_server import start_coap_server
from devices.coap_device import start_coap_device_loop

def initial_data_parser(path_to_file, how_many_rows_to_read):
    # enforce minimum
    if how_many_rows_to_read < 100:
        how_many_rows_to_read = 100

    out_files = {
        "humidity": Path("parsed_data_humidity_sensors.csv"),
        "light": Path("parsed_data_light_sensors.csv"),
        "temperature": Path("parsed_data_temperature_sensors.csv"),
    }

    # Open writers and write headers (overwrite existing files)
    writers = {}
    files = {}
    try:
        files["humidity"] = out_files["humidity"].open("w", newline="", encoding="utf-8")
        files["light"] = out_files["light"].open("w", newline="", encoding="utf-8")
        files["temperature"] = out_files["temperature"].open("w", newline="", encoding="utf-8")

        writers["humidity"] = csv.writer(files["humidity"])
        writers["light"] = csv.writer(files["light"])
        writers["temperature"] = csv.writer(files["temperature"])

        writers["humidity"].writerow(["time", "date", "humidity"])
        writers["light"].writerow(["time", "date", "light"])
        writers["temperature"].writerow(["time", "date", "temperature"])

        counts = {"humidity": 0, "light": 0, "temperature": 0}
        with open(path_to_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= how_many_rows_to_read:
                    break
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                # Expected: date, time, epoch, moteid, temperature, humidity, light, voltage
                if len(parts) < 8:
                    continue
                date, time = parts[0], parts[1]
                moteid = parts[3] # will not use it, progresses to slow (too many records :( )
                temperature = parts[4]
                humidity = parts[5]
                light = parts[6]

                chosen = random.choice(["humidity", "light", "temperature"])
                if chosen == "humidity":
                    writers["humidity"].writerow([time, date, humidity])
                elif chosen == "light":
                    writers["light"].writerow([time, date, light])
                else:
                    writers["temperature"].writerow([time, date, temperature])
                counts[chosen] += 1

        return counts

    finally:
        for fh in files.values():
            try:
                fh.close()
            except Exception:
                pass

def main():
    # Read configuration from config.json (in the current working directory)
    config_path = Path("config.json")
    if not config_path.exists():
        print("Configuration file 'config.json' not found.")
        return

    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print("Failed to read config.json:", e)
        return

    # Required fields
    path = cfg.get("path_to_data_file")
    if not path:
        print("'path_to_data_file' not set in config.json")
        return

    # rows_to_read (enforce integer and minimum inside parser too)
    try:
        rows = int(cfg.get("rows_to_read", 100))
    except (TypeError, ValueError):
        rows = 100

    # Read and keep other parameters (MQTT-focused)
    num_devices_mqtt = cfg.get("num_devices_mqtt")
    message_interval_mqtt = cfg.get("message_interval_mqtt")
    mqtt_broker = cfg.get("mqtt_broker")
    mqtt_topic = cfg.get("mqtt_topic")

    config_summary = {
        "path_to_data_file": path,
        "rows_to_read": rows,
        "num_devices_mqtt": num_devices_mqtt,
        "message_interval_mqtt": message_interval_mqtt,
        "mqtt_broker": mqtt_broker,
        "mqtt_topic": mqtt_topic,
    }

    print("Loaded configuration:")
    for k, v in config_summary.items():
        print(f"  {k}: {v}")

    counts = initial_data_parser(path, rows)
    print("Parsing finished. Rows written per file:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    # Sensor files map
    sensor_files = {
        "humidity": Path("parsed_data_humidity_sensors.csv"),
        "light": Path("parsed_data_light_sensors.csv"),
        "temperature": Path("parsed_data_temperature_sensors.csv"),
    }

    devices = []
    # MQTT-only flow
    # initialize/overwrite output CSV so each run starts fresh
    initialize_output("all_devices_recorded_data.csv")
    # ensure storage points at the same file
    set_output_file("all_devices_recorded_data.csv")
    # start local broker
    broker_host = mqtt_broker or "localhost"
    local_broker = LocalBroker(host=broker_host, port=1883)
    local_broker.start()
    print(f"Local MQTT broker started at {broker_host}:1883")
    # Start MQTT collector
    broker = mqtt_broker or "localhost"
    topic = mqtt_topic or "iot"
    mqtt_col = MqttCollector(broker_host=broker, topic=topic)
    mqtt_col.start()
    print(f"MQTT collector started and subscribed to topic '{topic}' on {broker}:1883")

    # fault injection params (optional) - apply into the faults module so all devices/pollers see them
    try:
        LOSS_RATE = float(cfg.get('loss_rate', 0.0))
        LATENCY_RANGE = tuple(cfg.get('latency_range', (0, 0)))
        FAIL_PROB = float(cfg.get('fail_prob', 0.0))
    except Exception:
        LOSS_RATE = 0.0
        LATENCY_RANGE = (0, 0)
        FAIL_PROB = 0.0

    # propagate configured values into the faults module globals
    try:
        faults.LOSS_RATE = LOSS_RATE
        faults.LATENCY_RANGE = LATENCY_RANGE
        faults.FAIL_PROB = FAIL_PROB
        print(f"Applied fault injection settings: LOSS_RATE={faults.LOSS_RATE}, LATENCY_RANGE={faults.LATENCY_RANGE}, FAIL_PROB={faults.FAIL_PROB}")
    except Exception:
        # If faults module can't be updated, continue with defaults
        print('Warning: could not apply fault injection settings to faults module')

    # initialize sent log
    initialize_sent_log()

    num_mqtt = int(num_devices_mqtt) if num_devices_mqtt else 0
    for i in range(1, num_mqtt + 1):
        device_id = "id_device" if i == 1 else f"id_device{i}"
        t = start_mqtt_device_thread(
            device_id=device_id,
            sensor_files=sensor_files,
            broker_host=broker,
            topic=topic,
            fixed_interval=(None if message_interval_mqtt == -1 else int(message_interval_mqtt)),
        )
        devices.append(t)

    # start Modbus simulated devices and poller (spawn N devices)
    modbus_targets = []
    num_modbus = int(cfg.get('num_devices_modbus', 1))
    for i in range(1, num_modbus + 1):
        port = 1501 + i  # start ports at 1502,1503,...
        device_id = 'modbus1' if i == 1 else f'modbus{i}'
        start_modbus_device_thread(host='127.0.0.1', port=port, unit_id=1, update_interval=5)
        modbus_targets.append({'host': '127.0.0.1', 'port': port, 'device_id': device_id})
    modbus_poller = ModbusPoller(modbus_targets, poll_interval=5)
    modbus_poller.start()

    # start CoAP gateway server and spawn N CoAP devices
    coap_server_thread = start_coap_server()
    num_coap = int(cfg.get('num_devices_coap', 1))
    coap_device_threads = []
    for i in range(1, num_coap + 1):
        device_id = 'coap1' if i == 1 else f'coap{i}'
        t = start_coap_device_loop('coap://127.0.0.1/gateway', device_id=device_id, sensor_files=None, interval=5)
        coap_device_threads.append(t)

    print(f"Simulating {num_mqtt} MQTT devices, {num_coap} CoAP devices and {num_modbus} Modbus devices")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping MQTT devices and collector...")
        for t in devices:
            t.stop()
        for t in devices:
            t.join()
        mqtt_col.stop()
        local_broker.stop()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()