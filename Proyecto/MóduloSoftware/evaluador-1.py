# UMBRALES DE PRUEBA (NO PRESCRIPCIÓN CLÍNICA):

SENTADILLA_MIN_FLEXION = 130
SENTADILLA_MAX_FLEXION = 150
SENTADILLA_EXTENSION = 160

FASE_1 = "Fase 1: Apertura de brazos"
FASE_2 = "Fase 2: Elevación de brazo"
FASE_3 = "Fase 3: Sentadilla bilateral"


def evaluar_ejercicio(ejercicio, angulos):
    if ejercicio == FASE_1:
        separacion = angulos.get("Separación codos")
        if separacion is None:
            return "ESPERANDO MOVIMIENTO", "Colócate de frente para medir ambos codos y hombros"
        if 0 <= separacion <= 1.0:
            return "ESPERANDO MOVIMIENTO", "Brazos cerrados; ahora ábrelos manteniéndolos elevados"
        if 2.0 <= separacion <= 3.0:
            codo_i = angulos.get("Codo izquierdo")
            codo_d = angulos.get("Codo derecho")
            if codo_i is None or codo_d is None:
                return "ESPERANDO MOVIMIENTO", "Mantén ambos codos visibles"
            if 80 <= codo_i <= 100 and 80 <= codo_d <= 100:
                return "MOVIMIENTO CORRECTO", "Apertura detectada; vuelve a cerrar los brazos"
            return "CORREGIR POSTURA", "Apertura detectada; comprueba flexión cercana a 90° en ambos codos"
        return "ESPERANDO MOVIMIENTO", "En transición entre cerrado y abierto"

    if ejercicio == FASE_2:
        codo = angulos.get("Codo izquierdo")
        arriba = angulos.get("Brazo izquierdo arriba")
        if codo is None:
            return "ESPERANDO MOVIMIENTO", "No se detecta el codo izquierdo"
        if 80 <= codo <= 100:
            return "ESPERANDO MOVIMIENTO", "Posicion L detectada; extiende el brazo izquierdo hacia arriba"
        if 160 <= codo <= 180:
            if arriba is None:
                return "ESPERANDO MOVIMIENTO", "Muestra hombro, codo y muneca izquierdos"
            if arriba:
                return "MOVIMIENTO CORRECTO", "Brazo izquierdo extendido hacia arriba; vuelve a la L"
            return "CORREGIR POSTURA", "Extiende el brazo izquierdo hacia arriba, no hacia abajo"
        return "ESPERANDO MOVIMIENTO", "En transicion entre la L y la extension"

    if ejercicio == FASE_3:
        # Recupera la regla original de la sentadilla: flexión de rodilla 75°–110°.
        valor = angulos.get("Rodilla derecha")
        if valor is None:
            return "ESPERANDO MOVIMIENTO", "No se detecta la rodilla derecha"
        if SENTADILLA_MIN_FLEXION <= valor <= SENTADILLA_MAX_FLEXION:
            return "MOVIMIENTO CORRECTO", "Flexión de rodilla detectada (sentadilla superficial de prueba)"
        return "CORREGIR POSTURA", "Fuera del rango objetivo de prueba; podría ser inicio o retorno"

    return "ESPERANDO MOVIMIENTO", "Selecciona un ejercicio válido"
