"""Análisis literario: convierte texto en eventos MIDI (nota e intensidad por oración)."""

import os
import re


def cargar_texto(ruta_archivo):
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_archivo}")
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        return f.read().strip()


def tokenizar_oraciones(texto):
    partes = re.split(r"[.!?;:]+", texto)
    return [p.strip() for p in partes if p and p.strip()]


def tokenizar_palabras(oracion):
    return re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", oracion)


def suma_ascii(palabra):
    return sum(ord(c) for c in palabra)


def _metrica_base(palabras):
    if not palabras:
        return 0.0
    return sum(len(p) * suma_ascii(p) for p in palabras) / len(palabras)


def _densidad_lexica(palabras):
    if not palabras:
        return 0.0
    total = len(palabras)
    unicas = len(set(p.lower() for p in palabras))
    promedio_long = sum(len(p) for p in palabras) / total
    return (unicas / total) * promedio_long


def cuantificar_oracion(oracion):
    palabras = tokenizar_palabras(oracion)
    if not palabras:
        return 0.0
    base = _metrica_base(palabras)
    densidad = _densidad_lexica(palabras)
    return base * (1 + densidad)


def normalizar_lista(valores):
    if not valores:
        return []
    minimo = min(valores)
    maximo = max(valores)
    if maximo == minimo:
        return [64 for _ in valores]
    return [
        max(0, min(127, int(round(((v - minimo) / (maximo - minimo)) * 127))))
        for v in valores
    ]


def analizar_texto(texto, nombre_nodo):
    oraciones = tokenizar_oraciones(texto)
    valores_brutos = [cuantificar_oracion(o) for o in oraciones]
    conteos_palabras = [len(tokenizar_palabras(o)) for o in oraciones]
    notas_midi = normalizar_lista(valores_brutos)
    intensidades_midi = normalizar_lista(conteos_palabras)

    eventos = []
    for i, oracion in enumerate(oraciones, start=1):
        nota = notas_midi[i - 1]
        intensidad = intensidades_midi[i - 1]
        print(
            f"  [{i:>4}] nota={nota:>3} | intensidad={intensidad:>3} "
            f"| bruto={valores_brutos[i-1]:.1f} | {oracion[:60]}"
        )
        eventos.append({
            "nodo": nombre_nodo,
            "oracion_num": i,
            "nota_midi": nota,
            "intensidad_midi": intensidad,
            "texto_original": oracion,
        })
    return eventos


def analizar_archivo(ruta_archivo, nombre_nodo):
    texto = cargar_texto(ruta_archivo)
    return analizar_texto(texto, nombre_nodo)


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(__file__))
    ruta = os.path.join(base, "texto", "quijote.txt")
    eventos = analizar_archivo(ruta, "quijote")
    print(f"\nTotal eventos: {len(eventos)}")
