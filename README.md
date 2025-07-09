# Overview

== YOU SHOULD NOT BUY THIS PRODUCT, BECAUSE IF THE SUBSCRIPTION ENDS THE PRODUCT WILL STOP WORKING AFTER A WHILE! (FOR EXAMPLE, WHEN IT IS NECESSARY TO CHANGE THE BATTERIES, IT IS NOT POSSIBLE TO DO IT WITHOUT A SUBSCRIPTION!!) ==

This program can be used to parse OWL Intuition packets (https://www.theowl.com/index.php/owl-intuition/), and publish to a mqtt server.

By default, it listen in multicast OWL address, but it you configure the push notifications (in https://www.owlintuition.com/) your server, you can listen in unicast by defining the owl\_multicast=0 and owl\_listen\_ip.

# Configuration
All configuration is set through environment variables.

You can set `OWL2MQTT_DEBUG` to `1` in order to get logging on `stderr` (which you'll see in the docker output).

## Data from OWL Intuition
The OWL Intution devices can send their data out on the local network. By default, this is by multicast to group `224.192.32.19` on port `22600`. You can change this at https://www.owlintuition.com/ by going to `System > Advanced Settings > Setup Data Push` and setting the `IP Address` and `Port Number`.

Use this configuration to either pass the following environment variables:
* Multicast (default)
    ```sh
    OWL2MQTT_OWL_MULTICAST=1
    OWL2MQTT_OWL_GROUP=224.192.32.19
    OWL2MQTT_OWL_PORT=22600
    ```
* Unicast
    ```sh
    OWL2MQTT_OWL_MULTICAST=0
    OWL2MQTT_OWL_LISTEN_IP=10.0.0.5
    OWL2MQTT_OWL_PORT=22600
    ```

## Data to MQTT
You set the MQTT broker server as follows:
```sh
OWL2MQTT_MQTT_ADDRESS=10.0.0.8
OWL2MQTT_MQTT_PORT=1883
OWL2MQTT_MQTT_USERNAME=optional-username
OWL2MQTT_MQTT_PASSWORD=optional-password
```

It will publish the state to the `/owl` topic and configuration to `/homeassistant/sensor`. If Home Assistant is listening to the MQTT broker, it will auto configure and appear as the `OWL Intution` device.

This currently presumes a CM180 device.

# Installation
1. Clone the repo
    ```sh
    cd /opt
    sudo git clone https://github.com/fapgomes/owl2mqtt.git
    ```
2. Build the Docker Image
    ```sh
    docker build -t owl2mqtt .
    ```
3. Run the Docker Container in the foreground with the desired configuration
    ```sh
    docker run --net=host \
      -e OWL2MQTT_MQTT_ADDRESS=... \
      -e OWL2MQTT_OWL_MULTICAST=... \
      -e OWL2MQTT_DEBUG=... \
      owl2mqtt
    ```

# openhab mqtt config example
owl.things
```
Bridge mqtt:broker:rabbitmq "MQTT Broker: RabbitMQ"
[
    host="localhost",
    port=1883,
    secure="AUTO",
    username="openhab",
    password="testpassword"
]
{
    // owl2mqtt
    Thing topic owl2mqtt "OWL" @ "Piso 1" {
    Channels:
        Type datetime   : timestamp             "OWL Timestamp"                 [ stateTopic="owl/electricity/timestamp" ]
        Type number     : battery               "OWL Battery"                   [ stateTopic="owl/electricity/battery" ]
        Type number     : rssi                  "OWL RSSI"                      [ stateTopic="owl/electricity/rssi" ]
        Type number     : lqi                   "OWL LQI"                       [ stateTopic="owl/electricity/lqi" ]
        Type number     : channel0              "OWL Channel 0"                 [ stateTopic="owl/electricity/channel0" ]
        Type number     : channel1              "OWL Channel 1"                 [ stateTopic="owl/electricity/channel1" ]
        Type number     : channel2              "OWL Channel 2"                 [ stateTopic="owl/electricity/channel2" ]
        Type number     : daychannel0           "OWL Day Channel 0"             [ stateTopic="owl/electricity/daychannel0" ]
        Type number     : daychannel1           "OWL Day Channel 1"             [ stateTopic="owl/electricity/daychannel1" ]
        Type number     : daychannel2           "OWL Day Channel 2"             [ stateTopic="owl/electricity/daychannel2" ]
    }
 }
 ```
 owl.items
 ```
 Group                   gOwl                        "Owl"       <energy>
Group:Number:SUM        gBombaCalorEnergy           "Consumo Energético Bomba Calor [%d w]"     <bomba_calor>
Group:Number:SUM        gBombaCalorEnergyDay        "Consumo Energético Bomba Calor Dia [%d w]" <bomba_calor>
DateTime                owlTimeStamp                "Time [%1$tY-%1$tm-%1$td  %1$tH:%1$tM]"     <time>                  (gOwl)                      { channel="mqtt:topic:rabbitmq:owl2mqtt:timestamp" }
Number                  owlBattery                  "Battery [%.1f %%]"                         <battery>               (gOwl)                      { channel="mqtt:topic:rabbitmq:owl2mqtt:battery" }
Number                  owlFase1                    "Fase 1 [%.1f w]"                           <energy>                (gOwl,gBombaCalorEnergy)    { channel="mqtt:topic:rabbitmq:owl2mqtt:channel0" }
Number                  owlFase1Day                 "Fase 1 dia [%.1f wh]"                      <energy>                (gOwl,gBombaCalorEnergyDay) { channel="mqtt:topic:rabbitmq:owl2mqtt:daychannel0" }
Number                  owlFase2                    "Fase 2 [%.1f w]"                           <energy>                (gOwl,gBombaCalorEnergy)    { channel="mqtt:topic:rabbitmq:owl2mqtt:channel1" }
Number                  owlFase2Day                 "Fase 2 dia [%.1f wh]"                      <energy>                (gOwl,gBombaCalorEnergyDay) { channel="mqtt:topic:rabbitmq:owl2mqtt:daychannel1" }
Number                  owlFase3                    "Fase 3 [%.1f w]"                           <energy>                (gOwl,gBombaCalorEnergy)    { channel="mqtt:topic:rabbitmq:owl2mqtt:channel2" }
Number                  owlFase3Day                 "Fase 3 dia [%.1f wh]"                      <energy>                (gOwl,gBombaCalorEnergyDay) { channel="mqtt:topic:rabbitmq:owl2mqtt:daychannel2" }
Number                  owlrssi                     "RSSI [%d]"                                 <qualityofservice>      (gOwl)                      { channel="mqtt:topic:rabbitmq:owl2mqtt:rssi" }
Number                  owllqi                      "lqi [%d]"                                  <qualityofservice>      (gOwl)                      { channel="mqtt:topic:rabbitmq:owl2mqtt:lqi" }
```
![Screenshot_20210323_160727](https://user-images.githubusercontent.com/39247306/112178710-e5941b00-8bf1-11eb-8791-71f7d7615a22.png)  
