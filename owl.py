import paho.mqtt.client as mqttClient
import socket
import struct
import json
import time
import configparser
from xml.etree import ElementTree
import syslog
import logging, sys

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

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

config = configparser.ConfigParser()
config.read('owl2mqtt.conf')

# for debugging only
DEBUG = int(config['global']['debug'])

OWL_PORT = int(config['owl']['owl_port'])
OWL_GROUP = config['owl']['owl_group']
OWL_LISTEN_IP = config['owl']['owl_listen_ip']
OWL_MULTICAST = config['owl']['owl_multicast']

broker_address = config['mqtt']['address']
broker_port = int(config['mqtt']['port'])
broker_username = config['mqtt'].get('username')
broker_password = config['mqtt'].get('password')

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
    sock.bind((OWL_GROUP, OWL_PORT))
    mreq = struct.pack(
        '4sl' if OWL_LISTEN_IP == '' else '4s4s',
        socket.inet_aton(OWL_GROUP),
        socket.INADDR_ANY if OWL_LISTEN_IP == '' else socket.inet_aton(OWL_LISTEN_IP))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
else:
    sock.bind((OWL_LISTEN_IP, OWL_PORT))

while True:
    client.loop()
    my_logging('Connected: ' + str(Connected))
    time.sleep(0.5)
    
    if Connected == 1:
        # Collect the XML multicast message
        xml, addr = sock.recvfrom(1024)
        # Parse the XML string
        root = ElementTree.fromstring(xml)

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

                client.publish("owl/"+root.tag+"/channel"+chan_value, current_value)
                client.publish("owl/"+root.tag+"/daychannel"+chan_value, day_value)
    else:
        client.connect(broker_address, port=broker_port)
        time.sleep(5)
