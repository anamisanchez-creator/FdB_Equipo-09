#include "BluetoothSerial.h"
#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth no habilitado en esta compilacion
#endif

BluetoothSerial SerialBT;
const int NUM_SENSORES = 4;
const int pinsEMG[NUM_SENSORES] = {34, 35, 32, 33};
const int pinBuzzer = 25; // Buzzer activo LOW-LEVEL TRIGGER
const int window_size = 5;
int valores[NUM_SENSORES][window_size] = {};
int indices[NUM_SENSORES] = {0, 0, 0, 0};
long sumas[NUM_SENSORES] = {0, 0, 0, 0};
const int threshold = 2000;
bool pressed[NUM_SENSORES] = {false, false, false, false};
unsigned long ultimoMuestreo = 0;
const unsigned long intervaloMuestreo = 20;

// Pitido no bloqueante: el muestreo sigue funcionando mientras suena.
const unsigned long duracionPitido = 120; // milisegundos
bool buzzerSonando = false;
unsigned long inicioPitido = 0;
String comandoBT = "";

void iniciarPitido() {
  digitalWrite(pinBuzzer, LOW); // LOW activa el modulo especificado
  inicioPitido = millis();
  buzzerSonando = true;
}

void procesarBluetooth() {
  while (SerialBT.available()) {
    char c = (char) SerialBT.read();
    if (c == '\n' || c == '\r') {
      comandoBT.trim();
      if (comandoBT == "BEEP") {
        iniciarPitido();
        Serial.println("[BUZZER] Repeticion registrada");
      }
      comandoBT = "";
    } else if (comandoBT.length() < 24) {
      comandoBT += c;
    } else {
      comandoBT = "";
    }
  }
}

void btCallback(esp_spp_cb_event_t event, esp_spp_cb_param_t *param) {
  if (event == ESP_SPP_SRV_OPEN_EVT) Serial.println(">>> [BT] Laptop conectada");
  else if (event == ESP_SPP_CLOSE_EVT) Serial.println(">>> [BT] Laptop desconectada");
}

void setup() {
  Serial.begin(115200);
  pinMode(pinBuzzer, OUTPUT);
  digitalWrite(pinBuzzer, HIGH); // Reposo: apagado
  SerialBT.register_callback(btCallback);
  if (!SerialBT.begin("ESP32_sEMG_Vest")) Serial.println("Error al iniciar Bluetooth");
  else Serial.println("Bluetooth listo: ESP32_sEMG_Vest");
}

void loop() {
  procesarBluetooth();
  unsigned long ahora = millis();
  if (buzzerSonando && ahora - inicioPitido >= duracionPitido) {
    digitalWrite(pinBuzzer, HIGH);
    buzzerSonando = false;
  }

  if (ahora - ultimoMuestreo >= intervaloMuestreo) {
    ultimoMuestreo = ahora;
    int promedios[NUM_SENSORES];
    for (int s = 0; s < NUM_SENSORES; s++) {
      int lectura = analogRead(pinsEMG[s]);
      sumas[s] -= valores[s][indices[s]];
      valores[s][indices[s]] = lectura;
      sumas[s] += lectura;
      indices[s] = (indices[s] + 1) % window_size;
      promedios[s] = sumas[s] / window_size;
    }

    char dataStream[48];
    snprintf(dataStream, sizeof(dataStream), "%d,%d,%d,%d",
             promedios[0], promedios[1], promedios[2], promedios[3]);
    Serial.println(dataStream);
    if (SerialBT.hasClient()) SerialBT.println(dataStream);

    // Preservamos los eventos de EMG originales: NO activan el buzzer.
    for (int s = 0; s < NUM_SENSORES; s++) {
      if (!pressed[s] && promedios[s] > threshold) {
        char mensaje[32];
        snprintf(mensaje, sizeof(mensaje), "COMANDO:FLEXION_CH%d", s + 1);
        Serial.println(mensaje);
        if (SerialBT.hasClient()) SerialBT.println(mensaje);
        pressed[s] = true;
      } else if (pressed[s] && promedios[s] < threshold * 0.8) {
        pressed[s] = false;
      }
    }
  }
}
