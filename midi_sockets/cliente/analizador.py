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
    notas_midi = normalizar_lista(valores_brutos)
    intensidades_midi = normalizar_lista(conteos_palabras)

    eventos = []
    for i, oracion in enumerate(oraciones, start=1):
        eventos.append(
            {
                "nodo": nombre_nodo,
                "oracion_num": i,
                "nota_midi": notas_midi[i - 1],
                "intensidad_midi": intensidades_midi[i - 1],
                "texto_original": oracion,
            }
        )
    return eventos


def analizar_archivo(ruta_archivo, nombre_nodo):
    texto = cargar_texto(ruta_archivo)
    return analizar_texto(texto, nombre_nodo)


def construir_reporte_visibilidad(texto, nombre_nodo, oracion_objetivo=None):
    """Genera una vista detallada del proceso de tokenización y cuantificación."""
    oraciones = tokenizar_oraciones(texto)
    valores_brutos = [cuantificar_oracion(o) for o in oraciones]
    conteos = [len(tokenizar_palabras(o)) for o in oraciones]
    notas_midi = normalizar_lista(valores_brutos)
    intensidades_midi = normalizar_lista(conteos)

    lineas = []
    lineas.append(f"=== REPORTE DE ANÁLISIS [{nombre_nodo}] ===")
    if oracion_objetivo is None:
        indices = list(range(len(oraciones)))
    else:
        indice = int(oracion_objetivo) - 1
        indices = [indice] if 0 <= indice < len(oraciones) else []

    if not indices:
        lineas.append(f"Oración {oracion_objetivo} no existe.")
        return "\n".join(lineas)

    lineas.append(f"Total de oraciones mostradas: {len(indices)}")

    for idx in indices:
        i = idx + 1
        oracion = oraciones[idx]
        palabras = tokenizar_palabras(oracion)
        lineas.append(f"\nOración {i}: {oracion}")
        lineas.append(f"Tokenización por palabra ({len(palabras)}):")
        if not palabras:
            lineas.append(" idx | token | len | suma_ascii | len*suma_ascii")
            lineas.append("   - | (sin palabras)")
        else:
            lineas.append(" idx | token           | len | suma_ascii | len*suma_ascii")
            lineas.append("-----+-----------------+-----+------------+---------------")
            for j, palabra in enumerate(palabras, start=1):
                ascii_total = suma_ascii(palabra)
                aporte = len(palabra) * ascii_total
                lineas.append(f"{j:>4} | {palabra:<15} | {len(palabra):>3} | {ascii_total:>10} | {aporte:>13}")
        lineas.append(f"Valor bruto: {valores_brutos[idx]:.2f}")
        lineas.append(
            f"Nota MIDI: {notas_midi[idx]} | Intensidad MIDI: {intensidades_midi[idx]}"
        )

    return "\n".join(lineas)


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(__file__))
    ruta = os.path.join(base, "texto", "quijote.txt")
    texto = cargar_texto(ruta)
    print(construir_reporte_visibilidad(texto, "quijote"))
