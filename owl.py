import paho.mqtt.client as mqttClient
import socket
import struct
import json
import time
import os
from xml.etree import ElementTree
import syslog
import logging, sys

# fetch settings from environment variables
DEBUG = int(os.getenv('OWL2MQTT_DEBUG', '0'))
OWL_PORT = int(os.getenv('OWL2MQTT_OWL_PORT', '22600'))
OWL_GROUP = os.getenv('OWL2MQTT_OWL_GROUP', '224.192.32.19')
OWL_LISTEN_IP = os.getenv('OWL2MQTT_OWL_LISTEN_IP', '')
OWL_MULTICAST = int(os.getenv('OWL2MQTT_OWL_MULTICAST', '1'))
broker_address = os.getenv('OWL2MQTT_MQTT_ADDRESS', 'localhost')
broker_port = int(os.getenv('OWL2MQTT_MQTT_PORT', '1883'))
broker_username = os.getenv('OWL2MQTT_MQTT_USERNAME')
broker_password = os.getenv('OWL2MQTT_MQTT_PASSWORD')

Connected = 0

def my_logging(msg):
    if DEBUG :
        logging.debug(msg)
    syslog.syslog(syslog.LOG_INFO, msg)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        my_logging('Connected to broker with the result code: ' + str(rc))
        global Connected                #Use global variable
        Connected = 1                   #Signal connection 
    else:
        my_logging('Connected to broker failed with the result code: ' + str(rc))

def on_disconnect(client, userdata, rc):
   global Connected
   Connected = 0

def on_publish(client, userdata, result):             #create function for callback
    if DEBUG :
        my_logging('Data published result: ' + str(result))
    pass

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, force=True)

my_logging('Starting owl2mqtt on ip: ' + OWL_LISTEN_IP)

client = mqttClient.Client("owl2mqtt client")
if broker_username and broker_password:
    client.username_pw_set(broker_username, password=broker_password)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish
client.connect(broker_address, port=broker_port)
time.sleep(5)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

if OWL_MULTICAST == 1:
    my_logging(f'Binding to multicast port: {OWL_GROUP}:{OWL_PORT}')
    sock.bind((OWL_GROUP, OWL_PORT))
    my_logging('Adding membership')
    mreq = struct.pack(
        '4sl' if OWL_LISTEN_IP == '' else '4s4s',
        socket.inet_aton(OWL_GROUP),
        socket.INADDR_ANY if OWL_LISTEN_IP == '' else socket.inet_aton(OWL_LISTEN_IP))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    my_logging('All ready')
else:
    my_logging(f'Binding to unicast port: {OWL_LISTEN_IP}:{OWL_PORT}')
    sock.bind((OWL_LISTEN_IP, OWL_PORT))

last_config_publish = 0

while True:
    client.loop()
    my_logging('Connected: ' + str(Connected))
    time.sleep(0.5)
    
    if Connected == 1:
        # Collect the XML multicast message
        xml, addr = sock.recvfrom(1024)
        # Parse the XML string
        #
        # It should follow this format:
        #   https://theowl.zendesk.com/hc/en-gb/article_attachments/200344663
        # found from the OWL documentation at:
        #   https://theowl.zendesk.com/hc/en-gb/articles/201284603-Multicast-UDP-API-Information
        #
        # e.g.
        # <electricity id='443719999999'>
        #   <signal rssi='-71' lqi='127' />
        #   <battery level='100%' />
        #   <chan id='0'><curr units='w'>483.00</curr><day units='wh'>10244.99</day></chan>
        #   <chan id='1'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan>
        #   <chan id='2'><curr units='w'>0.00</curr><day units='wh'>0.00</day></chan>
        # </electricity>
        #
        # it should be translated into MQTT messages like:
        #   topic                            sample data
        #   `owl/electricity/timestamp`      `1234567890`
        #   `owl/electricity/battery`        `100%`
        #   `owl/electricity/rssi`           `-71`
        #   `owl/electricity/lqi`            `127`
        #   `owl/electricity/channel0`       `483.0`
        #   `owl/electricity/daychannel0`    `10244.99`
        #   `owl/electricity/channel1`       `0.0`
        #   `owl/electricity/daychannel1`    `0.0`
        #   `owl/electricity/channel2`       `0.0`
        #   `owl/electricity/daychannel2`    `0.0`
        #
        # the configuration for a CM180 should be broadcast in Home Assistant compatible MQTT messages like:
        #   power topic: `homeassistant/sensor/owl_grid_phase1_power/config`
        # ```json
        # {
        #   "name": "Grid Phase 1 Power",
        #   "unique_id": "owl_grid_phase1_power",
        #   "state_topic": "owl/electricity/channel0",
        #   "unit_of_measurement": "W",
        #   "device_class": "power",
        #   "state_class": "measurement",
        #   "value_template": "{{ value | float }}",
        #   "device": {
        #     "identifiers": ["owlcm180"],
        #     "name": "OWL Intuition CM180",
        #     "model": "CM180"
        #   }
        # }
        # ```
        # and the same for `owl_grid_phase2_power` on `channel1` and `owl_grid_phase3_power` on `channel2`.
        # We also publish the combined power on `owl_grid_combined_power` which sums all three channels.
        #
        #   energy today topic: `homeassistant/sensor/owl_grid_phase1_energy_today/config`
        # ```json
        # {
        #   "name": "Grid Phase 1 Energy Today",
        #   "unique_id": "owl_grid_phase1_energy_today",
        #   "state_topic": "owl/electricity/daychannel0",
        #   "unit_of_measurement": "kWh",
        #   "device_class": "energy",
        #   "state_class": "measurement",
        #   "value_template": "{{ value | float / 1000 }}",
        #   "device": {
        #     "identifiers": ["owlcm180"],
        #     "name": "OWL Intuition CM180",
        #     "model": "CM180"
        #   }
        # }
        # ```
        # and the same for `owl_grid_phase2_energy_today` on `daychannel1` and `owl_grid_phase3_energy_today` on `daychannel2`.
        # We also publish the combined energy today on `owl_grid_combined_energy_today` which sums all three channels.
        #
        # As the `daychannel` values reset at midnight each day, we need to configure utility meters in Home Assistant.
        # Something like this in the Home Assistant `configuration.yaml`:
        # ```yaml
        # utility_meter:
        #   grid_energy_phase1:
        #     source: sensor.owl_grid_phase1_energy_today
        #     name: Grid Phase 1 Total
        #     cycle: daily
        #   grid_energy_phase2:
        #     source: sensor.owl_grid_phase2_energy_today
        #     name: Grid Phase 2 Total
        #     cycle: daily
        #   grid_energy_phase3:
        #     source: sensor.owl_grid_phase3_energy_today
        #     name: Grid Phase 3 Total
        #     cycle: daily
        #   grid_energy_total:
        #     source: sensor.owl_grid_combined_energy_today
        #     name: Grid Total Energy
        #     cycle: daily

        root = ElementTree.fromstring(xml)

        # Output the XML to debug log
        my_logging('Received XML: ' + ElementTree.tostring(root, encoding='unicode'))

        if root.tag == 'electricity' or root.tag == 'solar':
        
            timestamp_value = 0
            timestamp = root.find('timestamp')
            if timestamp is not None:
                timestamp_value = int(timestamp.text)
        
            battery_value = 0
            battery = root.find('battery')
            if battery is not None:
                battery_value = battery.attrib["level"]

            signal_rssi_value = 0
            signal_lqi_value = 0
            signal = root.find('signal')
            if signal is not None:
                signal_rssi_value = signal.attrib["rssi"]
                signal_lqi_value = signal.attrib["lqi"]

            my_logging('reading info, timestamp: ' + str(timestamp_value) + ', battery: ' + str(battery_value))
            client.publish("owl/"+root.tag+"/timestamp", timestamp_value)
            client.publish("owl/"+root.tag+"/battery", battery_value)
            client.publish("owl/"+root.tag+"/rssi", signal_rssi_value)
            client.publish("owl/"+root.tag+"/lqi", signal_lqi_value)

            total_power = 0.0
            total_energy_today = 0.0

            for chan in root.iter('chan'):
                chan_value = 0
                chan_value = chan.attrib["id"]

                current_value = 0.0
                current = chan.find('curr')
                if current is not None:
                    current_value = float(current.text)

                day_value = 0.0
                day = chan.find('day')
                if day is not None:
                    day_value = float(day.text)

                total_power += current_value
                total_energy_today += day_value

                client.publish("owl/"+root.tag+"/channel"+chan_value, current_value)
                client.publish("owl/"+root.tag+"/daychannel"+chan_value, day_value)

            # Round to 2 decimal places for power and energy values
            client.publish("owl/"+root.tag+"/channel_total", round(total_power, 2))
            client.publish("owl/"+root.tag+"/daychannel_total", round(total_energy_today, 2))

            # At most once a minute, publish the Home Assistant compatible config MQTT messages
            if time.time() - last_config_publish > 60:
                last_config_publish = time.time()

                config_data = [
                    {
                        "name": "Grid Phase 1 Power",
                        "id_prefix": "phase1_power",
                        "state_suffix": "channel0",
                    },
                    {
                        "name": "Grid Phase 2 Power",
                        "id_prefix": "phase2_power",
                        "state_suffix": "channel1",
                    },
                    {
                        "name": "Grid Phase 3 Power",
                        "id_prefix": "phase3_power",
                        "state_suffix": "channel2",
                    },
                    {
                        "name": "Grid Combined Power",
                        "id_prefix": "combined_power",
                        "state_suffix": "channel_total",
                    },
                    {
                        "name": "Grid Phase 1 Energy Today",
                        "id_prefix": "phase1_energy_today",
                        "state_suffix": "daychannel0",
                    },
                    {
                        "name": "Grid Phase 2 Energy Today",
                        "id_prefix": "phase2_energy_today",
                        "state_suffix": "daychannel1",
                    },
                    {
                        "name": "Grid Phase 3 Energy Today",
                        "id_prefix": "phase3_energy_today",
                        "state_suffix": "daychannel2",
                    },
                    {
                        "name": "Grid Combined Energy Today",
                        "id_prefix": "combined_energy_today",
                        "state_suffix": "daychannel_total",
                    }
                ]
              
                for each_config in config_data:
                    topic = f"homeassistant/sensor/owl_grid_{each_config['id_prefix']}/config"
                    payload = {
                        "name": each_config["name"],
                        "unique_id": f"owl_grid_{each_config['id_prefix']}",
                        "state_topic": f"owl/{root.tag}/{each_config['state_suffix']}",
                        "unit_of_measurement": "W" if "power" in each_config["id_prefix"] else "kWh",
                        "device_class": "power" if "power" in each_config["id_prefix"] else "energy",
                        "state_class": "measurement" if "power" in each_config["id_prefix"] else "total_increasing",
                        "value_template": "{{ value | float }}",
                        "device": {
                            "identifiers": ["owlcm180"],
                            "name": "OWL Intuition CM180",
                            "model": "CM180"
                        }
                    }
                    client.publish(topic, json.dumps(payload), qos=1, retain=True)
                    my_logging(f'Published Home Assistant config for {each_config["name"]} to {topic}')
    else:
        client.connect(broker_address, port=broker_port)
        time.sleep(5)
