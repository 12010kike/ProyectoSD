"""
Cliente TCP con menú interactivo para análisis, reproducción local y envío obligatorio al servidor.
"""

import os
import re
import socket
import time

from mido import Message, get_output_names, open_output

try:
    from analizador import analizar_archivo, cargar_texto, construir_reporte_visibilidad
except ImportError:
    from cliente.analizador import analizar_archivo, cargar_texto, construir_reporte_visibilidad


HOST = "127.0.0.1"
PUERTO = 5000

INSTRUMENTOS = [
    (0, "Piano acústico"),
    (24, "Guitarra acústica"),
    (40, "Violín"),
    (56, "Trompeta"),
    (73, "Flauta"),
    (118, "Synth Drum"),
]


class ClienteNodo:
    def __init__(
        self,
        nombre_nodo,
        host=HOST,
        puerto=PUERTO,
        pausa_segundos=0.25,
        visibilidad=False,
        sonar_local=False,
        programa_instrumento=0,
        puerto_midi=None,
    ):
        self.nombre_nodo = nombre_nodo
        self.host = host
        self.puerto = puerto
        self.pausa_segundos = pausa_segundos
        self.visibilidad = visibilidad
        self.sonar_local = sonar_local
        self.programa_instrumento = int(max(0, min(127, programa_instrumento)))
        self.puerto_midi = puerto_midi

        base = os.path.dirname(os.path.dirname(__file__))
        self.ruta_corpus = os.path.join(base, "corpus", f"{nombre_nodo}.txt")

    def _escapar(self, texto):
        return texto.replace("\\", r"\\").replace('"', r'\"').replace("\n", r"\n").replace("\t", r"\t")

    def _evento_a_json(self, evento):
        texto = self._escapar(str(evento["texto_original"]))
        return (
            "{"
            f'"nodo": "{evento["nodo"]}", '
            f'"oracion_num": {int(evento["oracion_num"])}, '
            f'"pitch": {int(evento["pitch"])}, '
            f'"velocity": {int(evento["velocity"])}, '
            f'"texto_original": "{texto}"'
            "}"
        )

    def _leer_respuesta(self, conexion):
        buffer = ""
        while "\n" not in buffer:
            data = conexion.recv(2048)
            if not data:
                break
            buffer += data.decode("utf-8", errors="replace")
        return buffer.split("\n", 1)[0].strip() if buffer else ""

    def _estado_respuesta(self, respuesta):
        m_estado = re.search(r'"estado"\s*:\s*"([^"]+)"', respuesta)
        m_detalle = re.search(r'"detalle"\s*:\s*"((?:\\.|[^"\\])*)"', respuesta)
        estado = m_estado.group(1) if m_estado else "desconocido"
        detalle = m_detalle.group(1) if m_detalle else ""
        detalle = detalle.replace(r"\\", "\\").replace(r'\"', '"').replace(r"\n", "\n")
        return estado, detalle

    def _mostrar_visibilidad(self):
        if not self.visibilidad:
            return
        texto = cargar_texto(self.ruta_corpus)
        print(construir_reporte_visibilidad(texto, self.nombre_nodo))
        print("=== FIN REPORTE ===\n")

    def _reproducir_evento_local(self, puerto, evento):
        note = int(evento["pitch"])
        vel = int(evento["velocity"])
        puerto.send(Message("note_on", note=note, velocity=vel))
        time.sleep(0.18)
        puerto.send(Message("note_off", note=note, velocity=0))

    def _reproducir_bloque_local(self, eventos):
        if not self.sonar_local:
            print(f"[{self.nombre_nodo}] Sonido local desactivado; no se puede reproducir.")
            return

        nombres = get_output_names()
        if not nombres:
            print(f"[{self.nombre_nodo}] No hay puertos MIDI de salida disponibles para reproducir.")
            return

        nombre_puerto = self.puerto_midi if self.puerto_midi in nombres else nombres[0]
        try:
            with open_output(nombre_puerto) as puerto:
                puerto.send(Message("program_change", program=self.programa_instrumento))
                print(
                    f"[{self.nombre_nodo}] Reproduciendo {len(eventos)} evento(s) "
                    f"en '{nombre_puerto}' con instrumento MIDI {self.programa_instrumento}..."
                )
                for evento in eventos:
                    self._reproducir_evento_local(puerto, evento)
                    time.sleep(0.05)
        except Exception as error:
            print(f"[{self.nombre_nodo}] Error al reproducir localmente: {error}")

    def _seleccionar_eventos(self, eventos, oracion_objetivo):
        if oracion_objetivo is None:
            return eventos
        seleccionados = [e for e in eventos if int(e["oracion_num"]) == int(oracion_objetivo)]
        if not seleccionados:
            print(f"[{self.nombre_nodo}] Oración {oracion_objetivo} no existe. Se enviarán todas.")
            return eventos
        return seleccionados

    def enviar_eventos(self, oracion_objetivo=None):
        eventos = analizar_archivo(self.ruta_corpus, self.nombre_nodo)
        if not eventos:
            print(f"[{self.nombre_nodo}] No hay eventos para enviar.")
            return

        self._mostrar_visibilidad()
        eventos_envio = self._seleccionar_eventos(eventos, oracion_objetivo)

        puerto_local = None
        if self.sonar_local:
            nombres = get_output_names()
            if not nombres:
                print(f"[{self.nombre_nodo}] No hay puertos MIDI de salida disponibles para sonido local.")
            else:
                nombre_puerto = self.puerto_midi if self.puerto_midi in nombres else nombres[0]
                try:
                    puerto_local = open_output(nombre_puerto)
                    puerto_local.send(Message("program_change", program=self.programa_instrumento))
                    print(
                        f"[{self.nombre_nodo}] Sonido local activo en '{nombre_puerto}' "
                        f"con instrumento MIDI {self.programa_instrumento}."
                    )
                except Exception as error:
                    print(f"[{self.nombre_nodo}] No se pudo abrir salida MIDI local: {error}")

        print(f"[{self.nombre_nodo}] Enviando {len(eventos_envio)} eventos a {self.host}:{self.puerto}...")
        enviados_ok = 0

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conexion:
                conexion.connect((self.host, self.puerto))
                for evento in eventos_envio:
                    if puerto_local is not None:
                        self._reproducir_evento_local(puerto_local, evento)

                    conexion.sendall((self._evento_a_json(evento) + "\n").encode("utf-8"))
                    estado, detalle = self._estado_respuesta(self._leer_respuesta(conexion))
                    if estado == "ok":
                        enviados_ok += 1
                        print(
                            f"[{self.nombre_nodo}] OK oración {evento['oracion_num']} "
                            f"(pitch={evento['pitch']}, velocity={evento['velocity']})"
                        )
                    else:
                        print(f"[{self.nombre_nodo}] ERROR oración {evento['oracion_num']}: {detalle}")

                    time.sleep(self.pausa_segundos)
        except Exception as error:
            print(f"[{self.nombre_nodo}] Error de conexión/envío: {error}")
            return
        finally:
            if puerto_local is not None:
                try:
                    puerto_local.close()
                except Exception:
                    pass

        print(f"[{self.nombre_nodo}] Finalizado: {enviados_ok}/{len(eventos_envio)} confirmados.")

        if enviados_ok > 0 and self.sonar_local and os.isatty(0):
            reproducir = input("¿Reproducir ahora la(s) oración(es) enviada(s)? [s/N]: ").strip().lower() == "s"
            if reproducir:
                self._reproducir_bloque_local(eventos_envio)


def _leer_entero_en_rango(mensaje, minimo, maximo, defecto):
    valor = input(mensaje).strip()
    if not valor:
        return defecto
    try:
        numero = int(valor)
    except ValueError:
        return defecto
    if numero < minimo or numero > maximo:
        return defecto
    return numero


def _menu_interactivo():
    print("=== MENÚ CLIENTE MIDI-SOCKETS ===")
    print("1) quijote")
    print("2) mio_cid")
    opcion = input("Selecciona obra [1-2] (Enter=1): ").strip()
    nodo = "mio_cid" if opcion == "2" else "quijote"

    print("\nOraciones a enviar:")
    print("1) Todas")
    print("2) Una oración específica")
    modo = input("Selecciona opción [1-2] (Enter=1): ").strip()
    oracion_objetivo = None
    if modo == "2":
        oracion_objetivo = _leer_entero_en_rango("Número de oración (>=1): ", 1, 10_000, 1)

    print("\nInstrumentos sugeridos:")
    for indice, (programa, nombre) in enumerate(INSTRUMENTOS, start=1):
        print(f"{indice}) {nombre} (programa {programa})")
    print("7) Escribir programa manual (0-127)")
    inst = input("Selecciona instrumento [1-7] (Enter=1): ").strip()

    programa = 0
    if inst == "7":
        programa = _leer_entero_en_rango("Programa MIDI (0-127): ", 0, 127, 0)
    else:
        idx = _leer_entero_en_rango("", 1, len(INSTRUMENTOS), 1)
        programa = INSTRUMENTOS[idx - 1][0]

    activar_sonido = input("¿Activar sonido local MIDI? [s/N]: ").strip().lower() == "s"
    ver = input("¿Mostrar reporte de tokenización? [S/n]: ").strip().lower() != "n"

    puertos = get_output_names() if activar_sonido else []
    puerto_midi = None
    if activar_sonido and puertos:
        print("\nPuertos MIDI disponibles:")
        for i, nombre in enumerate(puertos, start=1):
            print(f"{i}) {nombre}")
        idx_p = _leer_entero_en_rango("Selecciona puerto [1-n] (Enter=1): ", 1, len(puertos), 1)
        puerto_midi = puertos[idx_p - 1]

    return {
        "nodo": nodo,
        "oracion_objetivo": oracion_objetivo,
        "programa": programa,
        "sonar_local": activar_sonido,
        "visibilidad": ver,
        "puerto_midi": puerto_midi,
    }


def main():
    host = (os.getenv("HOST_SERVIDOR", HOST).strip() or HOST)
    puerto = int(os.getenv("PUERTO_SERVIDOR", str(PUERTO)))
    pausa = float(os.getenv("PAUSA_SEGUNDOS", "0.25"))
    usar_menu = os.getenv("MODO_MENU", "1").strip() == "1"

    if usar_menu:
        config = _menu_interactivo()
        cliente = ClienteNodo(
            nombre_nodo=config["nodo"],
            host=host,
            puerto=puerto,
            pausa_segundos=pausa,
            visibilidad=config["visibilidad"],
            sonar_local=config["sonar_local"],
            programa_instrumento=config["programa"],
            puerto_midi=config["puerto_midi"],
        )
        cliente.enviar_eventos(oracion_objetivo=config["oracion_objetivo"])
        return

    nodo = (os.getenv("NODO", "quijote").strip() or "quijote")
    visibilidad = os.getenv("VISIBILIDAD", "1").strip() == "1"
    sonar_local = os.getenv("SONAR_LOCAL", "0").strip() == "1"
    programa = int(os.getenv("PROGRAMA_MIDI", "0"))
    oracion_obj = os.getenv("ORACION_OBJETIVO", "").strip()
    oracion_objetivo = int(oracion_obj) if oracion_obj.isdigit() else None

    cliente = ClienteNodo(
        nombre_nodo=nodo,
        host=host,
        puerto=puerto,
        pausa_segundos=pausa,
        visibilidad=visibilidad,
        sonar_local=sonar_local,
        programa_instrumento=programa,
        puerto_midi=os.getenv("PUERTO_MIDI", "").strip() or None,
    )
    cliente.enviar_eventos(oracion_objetivo=oracion_objetivo)


if __name__ == "__main__":
    main()
