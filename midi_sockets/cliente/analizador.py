"""
Módulo de análisis literario para sonorización MIDI.
"""

import os
import re


def cargar_texto(ruta_archivo):
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_archivo}")
    with open(ruta_archivo, "r", encoding="utf-8") as archivo:
        return archivo.read().strip()


def tokenizar_oraciones(texto):
    partes = re.split(r"[.!?;:]+", texto)
    return [p.strip() for p in partes if p and p.strip()]


def tokenizar_palabras(oracion):
    return re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", oracion)


def suma_ascii(palabra):
    return sum(ord(c) for c in palabra)


def cuantificar_oracion(oracion):
    palabras = tokenizar_palabras(oracion)
    if not palabras:
        return 0.0
    valores = [len(p) * suma_ascii(p) for p in palabras]
    return sum(valores) / len(valores)


def normalizar_lista(valores):
    if not valores:
        return []
    minimo = min(valores)
    maximo = max(valores)
    if maximo == minimo:
        return [64 for _ in valores]
    salida = []
    for v in valores:
        norm = ((v - minimo) / (maximo - minimo)) * 127
        salida.append(max(0, min(127, int(round(norm)))))
    return salida


def analizar_texto(texto, nombre_nodo):
    oraciones = tokenizar_oraciones(texto)
    valores_brutos = [cuantificar_oracion(o) for o in oraciones]
    conteos_palabras = [len(tokenizar_palabras(o)) for o in oraciones]
    pitches = normalizar_lista(valores_brutos)
    velocities = normalizar_lista(conteos_palabras)

    eventos = []
    for i, oracion in enumerate(oraciones, start=1):
        eventos.append(
            {
                "nodo": nombre_nodo,
                "oracion_num": i,
                "pitch": pitches[i - 1],
                "velocity": velocities[i - 1],
                "texto_original": oracion,
            }
        )
    return eventos


def analizar_archivo(ruta_archivo, nombre_nodo):
    texto = cargar_texto(ruta_archivo)
    return analizar_texto(texto, nombre_nodo)


def construir_reporte_visibilidad(texto, nombre_nodo):
    """Genera una vista detallada del proceso de tokenización y cuantificación."""
    oraciones = tokenizar_oraciones(texto)
    valores_brutos = [cuantificar_oracion(o) for o in oraciones]
    conteos = [len(tokenizar_palabras(o)) for o in oraciones]
    pitches = normalizar_lista(valores_brutos)
    velocities = normalizar_lista(conteos)

    lineas = []
    lineas.append(f"=== REPORTE DE ANÁLISIS [{nombre_nodo}] ===")
    lineas.append(f"Total de oraciones: {len(oraciones)}")

    for i, oracion in enumerate(oraciones, start=1):
        palabras = tokenizar_palabras(oracion)
        lineas.append(f"\nOración {i}: {oracion}")
        lineas.append(f"Palabras ({len(palabras)}): {palabras}")
        lineas.append(f"Valor bruto: {valores_brutos[i - 1]:.2f}")
        lineas.append(f"Pitch: {pitches[i - 1]} | Velocity: {velocities[i - 1]}")

    return "\n".join(lineas)


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(__file__))
    ruta = os.path.join(base, "corpus", "quijote.txt")
    texto = cargar_texto(ruta)
    print(construir_reporte_visibilidad(texto, "quijote"))
