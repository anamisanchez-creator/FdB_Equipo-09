# UMBRALES DE PRUEBA (NO PRESCRIPCIÓN CLÍNICA):

SENTADILLA_MIN_FLEXION = 130
SENTADILLA_MAX_FLEXION = 150
SENTADILLA_EXTENSION = 160

"""Conteo de repeticiones por fases. Umbrales experimentales."""

FASE_1 = "Fase 1: Apertura de brazos"
FASE_2 = "Fase 2: Elevación de brazo"
FASE_3 = "Fase 3: Sentadilla bilateral"


class ContadorRepeticiones:
    def __init__(self):
        self.repeticiones = 0
        self.fase = "inicio"
        self.lado = None
        self.ejercicio_previo = None

    def actualizar(self, ejercicio, angulos):
        if ejercicio != self.ejercicio_previo:
            self.repeticiones = 0
            self.fase = "inicio"
            self.lado = None
            self.ejercicio_previo = ejercicio

        if ejercicio == FASE_1:
            separacion = angulos.get("Separación codos")
            if separacion is None:
                return self.repeticiones

            cerrado = 0 <= separacion <= 1.0
            abierto = 2.0 <= separacion <= 3.0
            codo_i = angulos.get("Codo izquierdo")
            codo_d = angulos.get("Codo derecho")
            codos_en_rango = (codo_i is not None and codo_d is not None
                              and 80 <= codo_i <= 100 and 80 <= codo_d <= 100)

            if self.fase == "inicio":
                if cerrado:
                    self.fase = "cerrado"
            elif self.fase == "cerrado":
                if abierto and codos_en_rango:
                    self.fase = "abierto"
            elif self.fase == "abierto":
                if cerrado:
                    self.repeticiones += 1
                    self.fase = "cerrado"
            return self.repeticiones

        if ejercicio == FASE_2:
            codo = angulos.get("Codo izquierdo")
            arriba = angulos.get("Brazo izquierdo arriba")
            if codo is None:
                return self.repeticiones
            flexionado = 80 <= codo <= 100
            extendido_arriba = 160 <= codo <= 180 and arriba is True
            if self.fase == "inicio":
                if flexionado:
                    self.fase = "flexionado"
            elif self.fase == "flexionado":
                if extendido_arriba:
                    self.fase = "extendido"
            elif self.fase == "extendido":
                if flexionado:
                    self.repeticiones += 1
                    self.fase = "flexionado"
            return self.repeticiones

        # Fase 3 conserva la misma lógica de sentadilla.
        configuraciones = {
            FASE_3: ("Rodilla derecha", SENTADILLA_MIN_FLEXION, SENTADILLA_MAX_FLEXION, SENTADILLA_EXTENSION),
        }
        config = configuraciones.get(ejercicio)
        if config is None:
            return self.repeticiones
        articulacion, minimo, maximo, extension = config
        angulo = angulos.get(articulacion)
        if angulo is None:
            return self.repeticiones
        if self.fase == "inicio":
            if angulo >= extension:
                self.fase = "extendido"
        elif self.fase == "extendido":
            if minimo <= angulo <= maximo:
                self.fase = "flexionado"
        elif self.fase == "flexionado":
            if angulo >= extension:
                self.repeticiones += 1
                self.fase = "extendido"
        return self.repeticiones
