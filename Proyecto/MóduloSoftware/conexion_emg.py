"""Recepción Bluetooth SPP del ESP32 a través de puerto COM de Windows.

Acepta dos formatos por línea:
    455,1918,0,430
    CH1:455,CH2:1918,CH3:0,CH4:430
Los mensajes COMANDO:FLEXION_CHn no son lecturas ADC.
"""

import queue
import re
import threading
import time

import serial


class ConexionEMG:
    def __init__(self, puerto="COM4", baudrate=115200):
        self.puerto = puerto
        self.baudrate = baudrate
        self.datos = queue.Queue(maxsize=2000)
        self.conectado = False
        self.ultimo_error = ""
        self.ultimo_dato = 0.0
        self.ultimo_comando = None
        self._detener = threading.Event()
        self._hilo = None
        self._serial = None

    @staticmethod
    def interpretar(linea):
        linea = linea.strip()
        if linea.startswith("COMANDO:"):
            return None
        try:
            if linea.startswith("CH1:"):
                partes = linea.split(",")
                if len(partes) != 4:
                    return None
                datos = []
                for indice, parte in enumerate(partes, 1):
                    match = re.fullmatch(r"CH(\d+):\s*(\d+)", parte.strip())
                    if not match or int(match.group(1)) != indice:
                        return None
                    datos.append(int(match.group(2)))
            else:
                partes = linea.split(",")
                if len(partes) != 4:
                    return None
                datos = [int(parte.strip()) for parte in partes]
            if all(0 <= valor <= 4095 for valor in datos):
                return datos
        except ValueError:
            pass
        return None

    def iniciar(self):
        if self._hilo and self._hilo.is_alive():
            return
        self._detener.clear()
        self._hilo = threading.Thread(target=self._leer, daemon=True)
        self._hilo.start()

    def _leer(self):
        while not self._detener.is_set():
            try:
                with serial.Serial(self.puerto, self.baudrate, timeout=0.3) as conexion:
                    self._serial = conexion
                    self.conectado = True
                    self.ultimo_error = ""
                    print(f"[EMG] Conectado al ESP32 en {self.puerto}")
                    while not self._detener.is_set():
                        bruto = conexion.readline()
                        if not bruto:
                            continue
                        linea = bruto.decode("utf-8", errors="ignore").strip()
                        if linea.startswith("COMANDO:"):
                            self.ultimo_comando = linea
                            continue
                        lectura = self.interpretar(linea)
                        if lectura is None:
                            continue
                        self.ultimo_dato = time.monotonic()
                        if self.datos.full():
                            try:
                                self.datos.get_nowait()
                            except queue.Empty:
                                pass
                        self.datos.put_nowait(lectura)
            except (serial.SerialException, OSError) as error:
                self.ultimo_error = str(error)
                print(f"[EMG] Conexión no disponible en {self.puerto}: {error}")
            finally:
                self.conectado = False
                self._serial = None
            self._detener.wait(2)

    def sonar_repeticion(self):
        """Solicita un pitido en el ESP32 usando el puerto SPP ya abierto."""
        conexion = self._serial
        if not self.conectado or conexion is None or not conexion.is_open:
            return False
        try:
            conexion.write(b"BEEP\n")
            return True
        except (serial.SerialException, OSError) as error:
            self.ultimo_error = str(error)
            return False

    def detener(self):
        self._detener.set()
        self.conectado = False
        if self._hilo is not None and self._hilo.is_alive():
            self._hilo.join(timeout=1.0)
