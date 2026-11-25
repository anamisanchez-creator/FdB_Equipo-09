
import cv2
import mediapipe as mp
import customtkinter as ctk
import tkinter as tk
import time
import math
import queue
from collections import deque
from evaluador import evaluar_ejercicio
from contador import ContadorRepeticiones
from pathlib import Path
from PIL import Image, ImageTk
from conexion_emg import ConexionEMG

# ==========================================
# 1. CONFIGURACION MEDIAPIPE
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "pose_landmarker_lite.task"
VIDEOS = {
    "Fase 1: Apertura de brazos": BASE_DIR / "videos" / "fase1.mp4",
    "Fase 2: Elevación de brazo": BASE_DIR / "videos" / "fase2.mp4",
    "Fase 3: Sentadilla bilateral": BASE_DIR / "videos" / "fase3.mp4"
}

if not MODEL_PATH.exists():
    raise FileNotFoundError("No se encontro el modelo MediaPipe")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ==========================================
# 2. CONEXIONES Y ARTICULACIONES
# ==========================================

CONNECTIONS = [
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24),
    (23, 24),
    (23, 25), (25, 27),
    (24, 26), (26, 28),
    (27, 29), (29, 31),
    (28, 30), (30, 32),
    (27, 31), (28, 32)
]

ARTICULACIONES = {
    "Codo izquierdo": (11, 13, 15),
    "Codo derecho": (12, 14, 16),
    "Hombro izquierdo": (23, 11, 13),
    "Hombro derecho": (24, 12, 14),
    "Rodilla izquierda": (23, 25, 27),
    "Rodilla derecha": (24, 26, 28),
    "Cadera izquierda": (11, 23, 25),
    "Cadera derecha": (12, 24, 26)
}


def calcular_angulo(a, b, c):

    angulo = math.degrees(
        math.atan2(c[1] - b[1], c[0] - b[0]) -
        math.atan2(a[1] - b[1], a[0] - b[0])
    )

    angulo = abs(angulo)

    if angulo > 180:
        angulo = 360 - angulo

    return angulo


# ==========================================
# 3. APLICACION PRINCIPAL
# ==========================================

class SistemaPostural(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.title("Sistema de Monitoreo Postural")
        self.geometry("1400x900")
        self.minsize(1100, 750)
        self.state("zoomed")

        self.camara = None
        self.landmarker = None

        self.activo = False
        self.ultimo_timestamp = 0
        self.camera_image = None
        self.after_id = None
        self.video_demo = None
        self.video_demo_nombre = None
        self.video_demo_imagen = None
        self.video_demo_after_id = None

        self.repeticiones = 0
        self.fase_movimiento = "inicio"
        self.contador = ContadorRepeticiones()
        self.conexion_emg = ConexionEMG(puerto="COM4")

        self.historial_emg = deque(maxlen=250)
        self.crear_interfaz()
        self.conexion_emg.iniciar()
        self.after(100, self.actualizar_emg)

        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)


    # ======================================
    # 4. DISEÑO DE LA INTERFAZ
    # ======================================

    def crear_interfaz(self):
        # Dos vistas; no se destruyen al cambiar, para mantener la cámara activa.
        self.vista_actual = "nino"
        self.ejercicio_seleccionado = ctk.StringVar(value="Fase 1: Apertura de brazos")
        self.configure(fg_color="#171923")

        cabecera = ctk.CTkFrame(self, fg_color="#202536", corner_radius=0, height=75)
        cabecera.pack(fill="x")
        cabecera.pack_propagate(False)
        # LOGO REHAB-TRACKER
        ruta_logo = BASE_DIR / "assets" / "logo.png"

        self.logo_img = ctk.CTkImage(
            light_image=Image.open(ruta_logo),
            dark_image=Image.open(ruta_logo),
            size=(110, 70)
        )

        self.logo_label = ctk.CTkLabel(
            cabecera,
            image=self.logo_img,
            text=""
        )

        self.logo_label.pack(
            side="left",
            padx=15,
            pady=4
        )
        ctk.CTkLabel(cabecera, text="Rehabilitación interactiva", text_color="#CCD4E6", font=("Segoe UI", 16)).pack(side="left")
        self.boton_vista = ctk.CTkButton(cabecera, text="VISTA PROFESIONAL", width=180, command=self.cambiar_vista, fg_color="#2675B8")
        self.boton_vista.pack(side="right", padx=24, pady=13)

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="both", expand=True, padx=20, pady=15)
        self.contenedor.grid_rowconfigure(0, weight=1)
        self.contenedor.grid_columnconfigure(0, weight=1)
        self.vista_nino = ctk.CTkFrame(self.contenedor, fg_color="transparent")
        self.vista_profesional = ctk.CTkFrame(self.contenedor, fg_color="transparent")
        for vista in (self.vista_nino, self.vista_profesional):
            vista.grid(row=0, column=0, sticky="nsew")
        self.crear_vista_nino()
        self.crear_vista_profesional()
        self.vista_nino.tkraise()

    def crear_panel_demo(self, padre):
        panel = ctk.CTkFrame(
            padre,
            fg_color="#252B3B",
            corner_radius=15
        )

        ctk.CTkLabel(
            panel,
            text="VIDEO DEMOSTRATIVO",
            font=("Segoe UI", 17, "bold"),
            text_color="#9AFFFD"
        ).pack(pady=(12, 8))

        video = tk.Label(
            panel,
            text="Aquí aparecerá el ejercicio",
            font=("Segoe UI", 14),
            bg="#20232B",
            fg="white"
        )
        video.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 12)
        )
        return panel, video

    def crear_selector(self, padre):
        barra = ctk.CTkFrame(padre, fg_color="#252B3B", corner_radius=12)
        barra.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(barra, text="Ejercicio:", font=("Segoe UI", 15, "bold")).pack(
            side="left", padx=(18, 12), pady=10)
        selector = ctk.CTkOptionMenu(
            barra, values=["Fase 1: Apertura de brazos", "Fase 2: Elevación de brazo", "Fase 3: Sentadilla bilateral"],
            variable=self.ejercicio_seleccionado, width=230, height=35,
            fg_color="#2675B8", button_color="#1C5486")
        selector.pack(side="left", padx=5)
        return barra

    def crear_controles(self, padre):
        controles = ctk.CTkFrame(padre, fg_color="transparent")
        controles.pack(fill="x", pady=(8, 0))
        boton_iniciar = ctk.CTkButton(controles, text="INICIAR EJERCICIO", height=46, fg_color="#2675B8", command=self.iniciar_monitoreo)
        boton_iniciar.pack(side="left", fill="x", expand=True, padx=(0, 6))
        boton_detener = ctk.CTkButton(controles, text="FINALIZAR EJERCICIO", height=46, fg_color="#9B3838", hover_color="#752828", command=self.detener_monitoreo, state="disabled")
        boton_detener.pack(side="left", fill="x", expand=True, padx=(6, 0))
        return boton_iniciar, boton_detener

    def crear_vista_nino(self):
        vista = self.vista_nino
        self.crear_selector(vista)
        cuerpo = ctk.CTkFrame(vista, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=2)
        cuerpo.grid_columnconfigure(1, weight=3)
        cuerpo.grid_columnconfigure(2, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)

        camara = ctk.CTkFrame(cuerpo, fg_color="#252B3B", corner_radius=15)
        camara.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(camara, text="¡VAMOS, TÚ PUEDES! ⭐", text_color="#FFD984", font=("Segoe UI", 23, "bold")).pack(pady=(12, 8))
        self.video_nino = tk.Label(camara, text="Aquí aparecerás tú 😊", font=("Segoe UI", 17), bg="#20232B", fg="white")
        self.video_nino.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        panel_demo, self.demo_nino = self.crear_panel_demo(cuerpo)
        panel_demo.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        lateral = ctk.CTkFrame(cuerpo, fg_color="transparent")
        lateral.grid(row=0, column=2, sticky="nsew")
        lateral.grid_rowconfigure((0, 1), weight=1)
        lateral.grid_columnconfigure(0, weight=1)
        tarjeta_rep = ctk.CTkFrame(lateral, fg_color="#28374C", corner_radius=15)
        tarjeta_rep.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        ctk.CTkLabel(tarjeta_rep, text="REPETICIONES:", font=("Segoe UI", 16, "bold")).pack(pady=(20, 8))
        self.repeticiones_nino = ctk.CTkLabel(tarjeta_rep, text="0", font=("Segoe UI", 65, "bold"), text_color="#FFD984")
        self.repeticiones_nino.pack(expand=True)
        ctk.CTkLabel(tarjeta_rep, text="¡Cada movimiento cuenta!", text_color="#DDE8F5").pack(pady=(0, 17))

        tarjeta_emg = ctk.CTkFrame(lateral, fg_color="#28374C", corner_radius=15)
        tarjeta_emg.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        ctk.CTkLabel(tarjeta_emg, text="MI MÚSCULO 💪", font=("Segoe UI", 17, "bold")).pack(pady=(18, 8))
        # Estado del ESP32 en la vista infantil
        self.activacion_nino = ctk.CTkLabel(
            tarjeta_emg,
            text="Esperando sensores... 💜",
            text_color="#9AFFFD",
            font=("Segoe UI", 13, "bold")
        )
        self.activacion_nino.pack(pady=(5, 8))

        self.grafica_nino = self.crear_grafica_emg(tarjeta_emg, 180)

        estado = ctk.CTkFrame(vista, fg_color="#294339", corner_radius=12)
        estado.pack(fill="x", pady=(10, 0))
        self.mensaje_nino = ctk.CTkLabel(estado, text="¡Elige un ejercicio para empezar!", font=("Segoe UI", 20, "bold"), text_color="#E2FFF0")
        self.mensaje_nino.pack(pady=12)
        self.iniciar_nino, self.detener_nino = self.crear_controles(vista)

    def crear_vista_profesional(self):
        vista = self.vista_profesional
        self.crear_selector(vista)
        indicadores = ctk.CTkFrame(vista, fg_color="transparent")
        indicadores.pack(fill="x", pady=(0, 7))
        self.estado_label = self.crear_tarjeta(indicadores, "Estado", "En espera")
        self.camara_label = self.crear_tarjeta(indicadores, "Cámara", "Desconectada")
        self.deteccion_label = self.crear_tarjeta(indicadores, "Detección", "Inactiva")

        cuerpo = ctk.CTkFrame(vista, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=2)
        cuerpo.grid_columnconfigure(1, weight=3)
        cuerpo.grid_columnconfigure(2, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)

        panel_camara = ctk.CTkFrame(cuerpo, fg_color="#282B34", corner_radius=12)
        panel_camara.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        ctk.CTkLabel(panel_camara, text="SEGUIMIENTO CORPORAL", font=("Segoe UI", 15, "bold")).pack(pady=9)
        self.video_label = tk.Label(panel_camara, text="La cámara aparecerá aquí", font=("Segoe UI", 15), bg="#242424", fg="white")
        self.video_label.pack(fill="both", expand=True, padx=9, pady=(0, 9))

        panel_demo, self.demo_profesional = self.crear_panel_demo(cuerpo)
        panel_demo.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        panel_angulos = ctk.CTkScrollableFrame(cuerpo, width=215, corner_radius=12)
        panel_angulos.grid(row=0, column=2, sticky="nsew")
        ctk.CTkLabel(panel_angulos, text="ÁNGULOS ARTICULARES", font=("Segoe UI", 14, "bold")).pack(pady=10)
        self.angulos_labels = {}
        for nombre in ARTICULACIONES:
            tarjeta = ctk.CTkFrame(panel_angulos, corner_radius=8)
            tarjeta.pack(fill="x", padx=5, pady=3)
            ctk.CTkLabel(tarjeta, text=nombre, font=("Segoe UI", 12, "bold"),text_color="#A78BFA").pack(pady=(8, 1))
            valor = ctk.CTkLabel(tarjeta, text="-- °", font=("Segoe UI", 18, "bold"))
            valor.pack(pady=(0, 7))
            self.angulos_labels[nombre] = valor

        # Medición calibrar apertura/cierre de brazos.
        tarjeta_separacion = ctk.CTkFrame(panel_angulos, corner_radius=8)
        tarjeta_separacion.pack(fill="x", padx=5, pady=(12, 3))
        ctk.CTkLabel(tarjeta_separacion, text="SEPARACIÓN ENTRE CODOS", font=("Segoe UI", 12, "bold"), text_color="#9AFFFD").pack(pady=(8, 2))
        self.separacion_codos_label = ctk.CTkLabel(
            tarjeta_separacion, text="--", font=("Segoe UI", 22, "bold"))
        self.separacion_codos_label.pack(pady=(0, 7))

        inferior = ctk.CTkFrame(vista, fg_color="transparent")
        inferior.pack(fill="x", pady=(8, 0))
        panel_evaluacion = ctk.CTkFrame(inferior, corner_radius=12)
        panel_evaluacion.pack(side="left", fill="both", expand=True, padx=(0, 7))
        panel_evaluacion.grid_columnconfigure(0, weight=3)
        panel_evaluacion.grid_columnconfigure(1, weight=1)
        panel_evaluacion.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(panel_evaluacion, text="EVALUACIÓN DEL MOVIMIENTO", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=2, pady=(10, 4))
        bloque_estado = ctk.CTkFrame(panel_evaluacion, fg_color="transparent")
        bloque_estado.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.resultado_label = ctk.CTkLabel(bloque_estado, text="ESPERANDO MOVIMIENTO", font=("Segoe UI", 18, "bold"), text_color="#A78BFA")
        self.resultado_label.pack(pady=(0, 5))
        self.mensaje_evaluacion = ctk.CTkLabel(bloque_estado, text="Selecciona un ejercicio e inicia el monitoreo", font=("Segoe UI", 11), wraplength=400)
        self.mensaje_evaluacion.pack()
        bloque_rep = ctk.CTkFrame(panel_evaluacion, fg_color="#252B3B", corner_radius=10)
        bloque_rep.grid(row=1, column=1, sticky="nsew", padx=(0, 12), pady=(0, 10))
        self.contador_label = ctk.CTkLabel(bloque_rep, text="REPETICIONES: 0", font=("Segoe UI", 17, "bold"), text_color="#A78BFA")
        self.contador_label.pack(expand=True, padx=12, pady=8)

        panel_emg = ctk.CTkFrame(inferior, corner_radius=12, width=430, height=190)
        panel_emg.pack(side="right", fill="both", padx=(7, 0))
        panel_emg.pack_propagate(False)
        ctk.CTkLabel(panel_emg, text="ELECTROMIOGRAFÍA (EMG)", font=("Segoe UI", 13, "bold")).pack(pady=(5, 0))
        # Estado de conexión del ESP32
        self.estado_emg = ctk.CTkLabel(
            panel_emg,
            text="ESP32: Desconectado",
            text_color="#F87171",
            font=("Segoe UI", 13, "bold")
        )
        self.estado_emg.pack(pady=(0, 2))

        self.grafica_profesional = self.crear_grafica_emg(panel_emg, 100)
        self.boton_iniciar, self.boton_detener = self.crear_controles(vista)

    def crear_tarjeta(self, padre, titulo, valor):
        tarjeta = ctk.CTkFrame(padre, corner_radius=10)
        tarjeta.pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkLabel(tarjeta, text=titulo).pack(pady=(5, 0))
        etiqueta = ctk.CTkLabel(tarjeta, text=valor, font=("Segoe UI", 15, "bold"))
        etiqueta.pack(pady=(0, 6))
        return etiqueta

    def cambiar_vista(self):
        if self.vista_actual == "nino":
            self.vista_actual = "profesional"
            self.vista_profesional.tkraise()
            self.boton_vista.configure(text="VISTA INFANTIL")
        else:
            self.vista_actual = "nino"
            self.vista_nino.tkraise()
            self.boton_vista.configure(text="VISTA PROFESIONAL")

    def actualizar_botones(self, monitoreando):
        for boton in (self.boton_iniciar, self.iniciar_nino):
            boton.configure(state="disabled" if monitoreando else "normal")
        for boton in (self.boton_detener, self.detener_nino):
            boton.configure(state="normal" if monitoreando else "disabled")


    # ======================================
    # 6. INICIAR MONITOREO
    # ======================================

    def iniciar_monitoreo(self):

        if self.activo:
            return

        try:

            self.camara = cv2.VideoCapture(0, cv2.CAP_DSHOW)

            if not self.camara.isOpened():
                raise RuntimeError("No se pudo abrir la webcam")

            BaseOptions = mp.tasks.BaseOptions
            PoseLandmarker = mp.tasks.vision.PoseLandmarker
            PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
            RunningMode = mp.tasks.vision.RunningMode

            options = PoseLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(MODEL_PATH)
                ),
                running_mode=RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5
            )

            self.landmarker = PoseLandmarker.create_from_options(
                options
            )

            self.ultimo_timestamp = 0
            self.ejercicio_actual = self.ejercicio_seleccionado.get()
            self.repeticiones = 0
            self.fase_movimiento = "inicio"
            self.contador_label.configure(text="REPETICIONES: 0")
            self.repeticiones_nino.configure(text="0")

            self.contador = ContadorRepeticiones()

            self.activo = True

            self.estado_label.configure(text="Monitoreando")
            self.camara_label.configure(text="Conectada")

            self.actualizar_botones(True)

            self.actualizar_camara()
            if self.activo:
                self.actualizar_video_demo()

        except Exception as error:

            print("ERROR AL INICIAR:", repr(error))

            self.activo = False
            self.liberar_recursos()

            self.estado_label.configure(text="Error")
            self.camara_label.configure(text="Desconectada")
            self.deteccion_label.configure(text="Inactiva")

            self.actualizar_botones(False)

            self.video_label.configure(text=f"No se pudo iniciar:\n{error}", image="")
            self.video_nino.configure(text=f"No se pudo iniciar:\n{error}", image="")


    # ======================================
    # 7. ACTUALIZAR CAMARA
    # ======================================

    def actualizar_camara(self):

        if not self.activo:
            return

        ret, frame = self.camara.read()

        if not ret:
            self.detener_monitoreo()
            self.estado_label.configure(text="Error de cámara")
            return

        # Analizar imagen ORIGINAL: MediaPipe conserva izquierda/derecha anatómicas.
        # El espejo se aplicará al final, solo al mostrarla.

        height, width, _ = frame.shape

        rgb_frame = cv2.cvtColor(
            frame, cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        timestamp_ms = int(time.monotonic() * 1000)

        timestamp_ms = max(
            timestamp_ms, self.ultimo_timestamp + 1
        )
        self.ultimo_timestamp = timestamp_ms

        results = self.landmarker.detect_for_video(
            mp_image, timestamp_ms
        )

        angulos_actuales = {}
        separacion_codos = None

        if results.pose_landmarks:

            self.deteccion_label.configure(text="Detectado")

            for pose in results.pose_landmarks:

                # Distancia horizontal normalizada por ancho entre hombros.
                # Valores en unidades relativas (no centímetros ni grados).
                hombro_izq, hombro_der = pose[11], pose[12]
                codo_izq, codo_der = pose[13], pose[14]
                puntos = (hombro_izq, hombro_der, codo_izq, codo_der)
                if all(p.visibility >= 0.5 for p in puntos):
                    ancho_hombros = abs(hombro_izq.x - hombro_der.x)
                    if ancho_hombros > 0.02:
                        separacion_codos = abs(codo_izq.x - codo_der.x) / ancho_hombros

                # Fase 2: confirmar elevacion izquierda usando landmarks 2D.
                # Solo marcamos True cuando hombro, codo y muneca son visibles.
                muneca_izq = pose[15]
                if all(p.visibility >= 0.5 for p in (hombro_izq, codo_izq, muneca_izq)):
                    # y aumenta hacia abajo en la imagen.
                    angulos_actuales["Brazo izquierdo arriba"] = (
                        muneca_izq.y < codo_izq.y < hombro_izq.y
                    )

                # Dibujar puntos
                for landmark in pose:

                    if landmark.visibility < 0.5:
                        continue

                    x = int(landmark.x * width)
                    y = int(landmark.y * height)

                    cv2.circle(
                        frame, (x, y), 5, (0, 255, 0), -1
                    )

                # Dibujar conexiones
                for start_idx, end_idx in CONNECTIONS:

                    start = pose[start_idx]
                    end = pose[end_idx]

                    if (start.visibility < 0.5 or
                            end.visibility < 0.5):
                        continue

                    p1 = (
                        int(start.x * width),
                        int(start.y * height)
                    )

                    p2 = (
                        int(end.x * width),
                        int(end.y * height)
                    )

                    cv2.line(
                        frame, p1, p2, (255, 0, 0), 3
                    )

                # Calcular ángulos
                for nombre, indices in ARTICULACIONES.items():

                    a_idx, b_idx, c_idx = indices

                    a_lm = pose[a_idx]
                    b_lm = pose[b_idx]
                    c_lm = pose[c_idx]

                    if (a_lm.visibility > 0.5 and
                            b_lm.visibility > 0.5 and
                            c_lm.visibility > 0.5):

                        a = (
                            int(a_lm.x * width),
                            int(a_lm.y * height)
                        )

                        b = (
                            int(b_lm.x * width),
                            int(b_lm.y * height)
                        )

                        c = (
                            int(c_lm.x * width),
                            int(c_lm.y * height)
                        )

                        angulo = calcular_angulo(a, b, c)

                        angulos_actuales[nombre] = round(
                            angulo, 2
                        )

        else:

            self.deteccion_label.configure(text="No detectado")

        # Mostrar medición solo cuando están visibles ambos codos y hombros.
        if separacion_codos is None:
            self.separacion_codos_label.configure(text="--")
        else:
            self.separacion_codos_label.configure(text=f"{separacion_codos:.2f}")

        # Actualizar indicadores
        for nombre, etiqueta in self.angulos_labels.items():

            valor = angulos_actuales.get(nombre)
            if valor is not None:
                angulo_mostrado = round(valor, 1)
                etiqueta.configure(text=f"{angulo_mostrado} °")
            else:
                etiqueta.configure(text="-- °")
        # Actualizar el ejercicio seleccionado en tiempo real
        nuevo_ejercicio = self.ejercicio_seleccionado.get()

        if nuevo_ejercicio != self.ejercicio_actual:

            self.ejercicio_actual = nuevo_ejercicio

            self.contador = ContadorRepeticiones()
            self.repeticiones = 0  # Resetear también referencia del buzzer

            self.contador_label.configure(
                text="REPETICIONES: 0"
            )
            self.repeticiones_nino.configure(text="0")

        # Incorporar la distancia ya calculada para que la usen contador.py y evaluador.py
        angulos_actuales["Separación codos"] = separacion_codos

        # ======================================
        # CONTADOR Y EVALUADOR ACTUALIZADOS
        # ======================================
        # Los modulos ahora reconocen directamente Fase 1, Fase 2 y Fase 3.
        if results.pose_landmarks:
            repeticiones = self.contador.actualizar(
                self.ejercicio_actual, angulos_actuales
            )
            self.contador_label.configure(
                text=f"REPETICIONES: {repeticiones}"
            )
            self.repeticiones_nino.configure(text=str(repeticiones))

            # Pitido SOLO al aumentar el contador de repeticiones.
            if repeticiones > self.repeticiones:
                self.conexion_emg.sonar_repeticion()
            self.repeticiones = repeticiones

            estado, mensaje = evaluar_ejercicio(
                self.ejercicio_actual, angulos_actuales
            )
        else:
            estado = "ESPERANDO MOVIMIENTO"
            mensaje = "No se detecta el cuerpo"

        colores = {
            "MOVIMIENTO CORRECTO": "#16A34A",
            "CORREGIR POSTURA": "#DC2626",
            "ESPERANDO MOVIMIENTO": "#A78BFA"
        }

        self.resultado_label.configure(
            text=estado,
            text_color=colores[estado]
        )

        self.mensaje_evaluacion.configure(
            text=mensaje
        )
        mensajes_infantiles = {
            "MOVIMIENTO CORRECTO": "¡Muy bien! Sigue así ⭐",
            "CORREGIR POSTURA": "¡Inténtalo otra vez, tú puedes! 💜",
            "ESPERANDO MOVIMIENTO": "¡Ponte frente a la cámara! 😊"
        }
        self.mensaje_nino.configure(text=mensajes_infantiles.get(estado, "¡Vamos!"))

        # Espejo visual DESPUÉS de detectar ángulos y dibujar landmarks.
        frame = cv2.flip(frame, 1)

        # Mostrar cámara dentro de la interfaz
        imagen = Image.fromarray(
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        )

        # Ajustar a la zona visible; evita ampliar demasiado o desbordar.
        destino = self.video_nino if self.vista_actual == "nino" else self.video_label
        ancho = max(100, destino.winfo_width() - 10)
        alto = max(100, destino.winfo_height() - 10)
        imagen.thumbnail((ancho, alto))

        # Imagen de Tkinter: conservar una referencia válida por fotograma.
        self.camera_image = ImageTk.PhotoImage(imagen, master=self)
        self.video_label.configure(image=self.camera_image, text="")
        self.video_nino.configure(image=self.camera_image, text="")

        # Evitar saturar la interfaz con actualizaciones demasiado frecuentes.
        self.after_id = self.after(33, self.actualizar_camara)


    # ======================================
    # VIDEO DEMOSTRATIVO EN BUCLE
    # ======================================

    def mostrar_aviso_video(self, mensaje):
        for etiqueta in (self.demo_nino, self.demo_profesional):
            etiqueta.configure(image="", text=mensaje)

    def actualizar_video_demo(self):
        self.video_demo_after_id = None
        if not self.activo:
            return

        ejercicio = self.ejercicio_seleccionado.get()
        if ejercicio != self.video_demo_nombre:
            if self.video_demo is not None:
                self.video_demo.release()
            self.video_demo_nombre = ejercicio
            ruta = VIDEOS.get(ejercicio)
            self.video_demo = (cv2.VideoCapture(str(ruta))
                               if ruta is not None and ruta.is_file() else None)
            self.video_demo_fps = 30.0
            if self.video_demo is not None and self.video_demo.isOpened():
                fps = self.video_demo.get(cv2.CAP_PROP_FPS)
                if 1 <= fps <= 120:
                    self.video_demo_fps = fps

        if self.video_demo is not None and self.video_demo.isOpened():
            ok, frame = self.video_demo.read()
            if not ok:
                self.video_demo.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.video_demo.read()

            if ok:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                imagen = Image.fromarray(rgb)
                destino = self.demo_nino if self.vista_actual == "nino" else self.demo_profesional
                ancho = max(100, destino.winfo_width() - 10)
                alto = max(100, destino.winfo_height() - 10)
                imagen.thumbnail((ancho, alto))
                self.video_demo_imagen = ImageTk.PhotoImage(imagen, master=self)
                for etiqueta in (self.demo_nino, self.demo_profesional):
                    etiqueta.configure(image=self.video_demo_imagen, text="")
            else:
                self.mostrar_aviso_video("No se pudo leer el video")
        else:
            self.mostrar_aviso_video(f"No se encontró el video de {ejercicio}")

        intervalo_ms = max(8, int(1000 / self.video_demo_fps)) if self.video_demo else 250
        if self.activo:
            self.video_demo_after_id = self.after(intervalo_ms, self.actualizar_video_demo)

    # ======================================
    # 8. DETENER MONITOREO
    # ======================================

    def detener_monitoreo(self):

        self.activo = False
        # Cancelar actualizaciones pendientes de cámara
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.ultimo_timestamp = 0

        self.liberar_recursos()
        self.mostrar_aviso_video("Sesión finalizada")
        self.video_demo_imagen = None

        self.estado_label.configure(text="Finalizado")
        self.camara_label.configure(text="Desconectada")
        self.deteccion_label.configure(text="Inactiva")

        self.video_label.configure(image="", text="Sesión finalizada")
        self.video_nino.configure(image="", text="Sesión finalizada")
        self.mensaje_nino.configure(text="¡Buen trabajo! ⭐")

        self.camera_image = None

        for etiqueta in self.angulos_labels.values():
            etiqueta.configure(text="-- °")
        self.separacion_codos_label.configure(text="--")

        self.actualizar_botones(False)


    # ======================================
    # 9. LIBERAR RECURSOS
    # ======================================

    def liberar_recursos(self):

        if self.camara is not None:
            self.camara.release()
            self.camara = None

        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None

        if self.video_demo_after_id is not None:
            self.after_cancel(self.video_demo_after_id)
            self.video_demo_after_id = None
        if self.video_demo is not None:
            self.video_demo.release()
            self.video_demo = None
        self.video_demo_nombre = None
    COLORES_EMG = ("#38BDF8", "#FBBF24", "#4ADE80", "#F472B6")

    def crear_grafica_emg(self, padre, alto):
        leyenda = ctk.CTkFrame(padre, fg_color="transparent")
        leyenda.pack(fill="x", padx=6)
        for i, color in enumerate(self.COLORES_EMG):
            ctk.CTkLabel(leyenda, text=f"CH{i+1}", text_color=color,
                         font=("Segoe UI", 11, "bold")).pack(side="left", expand=True)
        canvas = tk.Canvas(padre, height=alto, width=180, bg="#171923",
                           highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        canvas.bind("<Configure>", lambda event: self.dibujar_emg(canvas))
        return canvas

    def dibujar_emg(self, canvas):
        canvas.delete("all")
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 80 or h < 55:
            return
        x0, x1, y0, y1 = 35, w-8, 8, h-22
        datos = list(self.historial_emg)
        # Escala automática común para los cuatro canales (unidades ADC).
        valores = [v for fila in datos for v in fila]
        techo = min(4095, max(500, math.ceil(max(valores, default=0)/500)*500))
        for i in range(5):
            y = y1 - (y1-y0)*i/4
            canvas.create_line(x0, y, x1, y, fill="#374151")
            canvas.create_text(x0-4, y, text=str(round(techo*i/4)),
                               anchor="e", fill="#BFCDE2", font=("Segoe UI", 8))
        for i in range(5):
            x = x0 + (x1-x0)*i/4
            canvas.create_line(x, y0, x, y1, fill="#303846")
        canvas.create_text((x0+x1)/2, h-9, text="Muestras recientes · ADC",
                           fill="#BFCDE2", font=("Segoe UI", 8))
        if not datos:
            canvas.create_text((x0+x1)/2, (y0+y1)/2, text="Sin señal",
                               fill="#BFCDE2")
            return
        for canal, color in enumerate(self.COLORES_EMG):
            puntos = []
            for j, fila in enumerate(datos):
                x = x1 - (len(datos)-1-j)*(x1-x0)/249
                y = y1 - fila[canal]*(y1-y0)/techo
                puntos.extend((x, y))
            if len(puntos) >= 4:
                canvas.create_line(*puntos, fill=color, width=1.5)
            else:
                x, y = puntos
                canvas.create_oval(x-2,y-2,x+2,y+2,fill=color,outline="")

    def actualizar_emg(self):
        try:
            recientes = (self.conexion_emg.conectado and
                         time.monotonic() - self.conexion_emg.ultimo_dato < 2.0)
            # Conservar todas las muestras disponibles, no solo la última.
            for _ in range(2000):
                try:
                    datos = self.conexion_emg.datos.get_nowait()
                except queue.Empty:
                    break
                if recientes:
                    self.historial_emg.append(tuple(datos))
            if not recientes:
                self.historial_emg.clear()
            for canvas in (self.grafica_nino, self.grafica_profesional):
                self.dibujar_emg(canvas)
            self.estado_emg.configure(text="ESP32: Conectado" if recientes else "ESP32: Sin señal",
                                      text_color="#4ADE80" if recientes else "#F87171")
            self.activacion_nino.configure(text="¡Sensores conectados! 💪" if recientes else "Esperando sensores... 💜",
                                           text_color="#4ADE80" if recientes else "#9AFFFD")
        except Exception as error:
            print("Error al actualizar EMG:", error)
        self.after(100, self.actualizar_emg)

    def cerrar_aplicacion(self):
        self.conexion_emg.detener()

        self.activo = False
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.liberar_recursos()
        self.destroy()

# ==========================================
# 10. EJECUTAR APLICACION
# ==========================================

if __name__ == "__main__":

    app = SistemaPostural()
    app.mainloop()
