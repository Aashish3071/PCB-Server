// ESP32 + DHT22 environmental sensor -> IoT platform over MQTT.
//
// Libraries (Arduino Library Manager): "PubSubClient" by Nick O'Leary,
// "DHT sensor library" by Adafruit (+ "Adafruit Unified Sensor").
//
// Fill in Wi-Fi, server address and the device access token
// (from credentials.json or Entities > Devices > <device> > Copy access token).

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

const char* WIFI_SSID     = "your-wifi";
const char* WIFI_PASSWORD = "your-wifi-password";
const char* MQTT_HOST     = "192.168.1.3";       // LAN IP of the computer running the platform (or cloud hostname)
const uint16_t MQTT_PORT  = 1883;
const char* DEVICE_TOKEN  = "DEVICE_ACCESS_TOKEN";

const uint8_t DHT_PIN = 4;
const unsigned long SEND_INTERVAL_MS = 30000;

DHT dht(DHT_PIN, DHT22);
WiFiClient net;
PubSubClient mqtt(net);
unsigned long lastSend = 0;

void connectWifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(500);
}

void connectMqtt() {
  while (!mqtt.connected()) {
    // The access token is the MQTT username; password is empty.
    if (!mqtt.connect("esp32-sensor", DEVICE_TOKEN, nullptr)) delay(5000);
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  connectWifi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();

  if (millis() - lastSend < SEND_INTERVAL_MS) return;
  lastSend = millis();

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT read failed");
    return;
  }
  char payload[128];
  snprintf(payload, sizeof(payload), "{\"temperature\":%.2f,\"humidity\":%.2f,\"rssi\":%d}",
           temperature, humidity, WiFi.RSSI());
  mqtt.publish("v1/devices/me/telemetry", payload);
  Serial.println(payload);
}
