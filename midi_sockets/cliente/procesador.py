"""
Procesador (Worker): recibe configuración del Monitor, analiza texto,
reproduce con FluidSynth y reporta eventos al Monitor.

Uso:
    python3 cliente/procesador.py procesador1
    python3 cliente/procesador.py procesador2
"""

import os
import queue
import random
import re
import socket
import sys
import threading
import time

from mido import Message, MidiFile, MidiTrack

HOST = "127.0.0.1"
PUERTO = 5000
BUFFER = 4096

_NOMBRES_NOTA = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _midi_a_note(numero_midi):
    from mingus.containers import Note
    nombre = _NOMBRES_NOTA[int(numero_midi) % 12]
    octava = max(0, int(numero_midi) // 12 - 1)
    return Note(nombre, octava)


class Procesador:
    def __init__(self, nombre, host=HOST, puerto=PUERTO):
        self.nombre = nombre
        self.host = host
        self.puerto = puerto
        self.sock = None
        self._buffer = ""
        self.lock_send = threading.Lock()
        self.cola = queue.Queue()

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ruta_textos = os.path.join(base, "texto")
        self.ruta_soundfont = os.path.join(base, "soundfonts", "FluidR3_GM.sf2")

    def _conectar(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.puerto))
        self._enviar_raw(f"IDENT {self.nombre}")
        resp = self._leer_linea_directa()
        if resp != "OK":
            raise ConnectionError(f"Servidor rechazó identificación: {resp}")
        print(f"[{self.nombre}] Conectado al servidor.")

    def _enviar_raw(self, mensaje):
        with self.lock_send:
            self.sock.sendall((mensaje + "\n").encode("utf-8"))

    def _leer_linea_directa(self):
        while "\n" not in self._buffer:
            data = self.sock.recv(BUFFER)
            if not data:
                raise ConnectionError("Servidor cerró la conexión")
            self._buffer += data.decode("utf-8", errors="replace")
        linea, self._buffer = self._buffer.split("\n", 1)
        return linea.strip()

    def _enviar_privado(self, destino, mensaje):
        # IMPORTANTE: el destino "monitor" debe coincidir con NOMBRE en monitor.py (línea 23)
        self._enviar_raw(f"/w {destino} {mensaje}")

    def _hilo_escucha(self):
        buf = self._buffer
        try:
            while True:
                data = self.sock.recv(BUFFER)
                if not data:
                    self.cola.put(None)
                    break
                buf += data.decode("utf-8", errors="replace")
                while "\n" in buf:
                    linea, buf = buf.split("\n", 1)
                    linea = linea.strip()
                    if linea:
                        self.cola.put(linea)
        except Exception as e:
            print(f"[{self.nombre}] Error en escucha: {e}")
            self.cola.put(None)

    def procesar_texto(self, ruta_archivo):
        from analizador import analizar_archivo

        nodo = os.path.splitext(os.path.basename(ruta_archivo))[0]
        print(f"[{self.nombre}] Analizando '{nodo}'...")
        eventos = analizar_archivo(ruta_archivo, nodo)
        print(f"[{self.nombre}] {len(eventos)} eventos listos.")
        return eventos, nodo

    def _init_fluidsynth(self, instrumento=0):
        if sys.platform == "darwin":
            dyld = os.environ.get("DYLD_LIBRARY_PATH", "")
            for brew_lib in ("/opt/homebrew/lib", "/usr/local/lib"):
                if os.path.isdir(brew_lib) and brew_lib not in dyld:
                    os.environ["DYLD_LIBRARY_PATH"] = brew_lib + (":" + dyld if dyld else "")
                    break

        from mingus.midi import fluidsynth

        if not os.path.isfile(self.ruta_soundfont):
            print(
                f"[{self.nombre}] SoundFont no encontrado: {self.ruta_soundfont}\n"
                f"  Coloca FluidR3_GM.sf2 en midi_sockets/soundfonts/"
            )
            return None

        driver = "coreaudio" if sys.platform == "darwin" else None
        if not fluidsynth.init(self.ruta_soundfont, driver=driver):
            print(f"[{self.nombre}] No se pudo inicializar FluidSynth.")
            return None

        fluidsynth.set_instrument(1, instrumento)
        return fluidsynth

    def sonar_texto(self, eventos, nodo, instrumento=0):
        fluidsynth = self._init_fluidsynth(instrumento)
        print(f"[{self.nombre}] Iniciando reproducción de {len(eventos)} eventos...")

        for evento in eventos:
            nota_raw = int(evento["nota_midi"])
            intensidad_raw = int(evento["intensidad_midi"])
            oracion_num = int(evento["oracion_num"])

            if intensidad_raw == 0:
                # Silencio explícito: puntuación o texto vacío
                print(f"  [{oracion_num:>4}] [SILENCIO — puntuación]")
                time.sleep(0.5)
            elif fluidsynth is not None:
                # Mapear nota al rango audible [36–84] (C2–C6)
                nota_audible = 36 + int(nota_raw * 48 / 127)
                # Escalar velocity [1,127] → [64,127]
                vel_playback = 64 + int(intensidad_raw * 63 / 127)
                note_obj = _midi_a_note(nota_audible)
                texto_corto = str(evento.get("texto_original", ""))[:60]
                print(
                    f"  [{oracion_num:>4}] {note_obj.name}{note_obj.octave} "
                    f"vel={intensidad_raw}→{vel_playback} | {texto_corto}"
                )
                fluidsynth.play_Note(note_obj, 1, vel_playback)
                time.sleep(2.5)
                fluidsynth.stop_Note(note_obj, 1)
                time.sleep(0.3)
            else:
                print(f"  [{oracion_num:>4}] nota={nota_raw} intensidad={intensidad_raw} (sin audio)")
                time.sleep(0.1)

            self._enviar_privado(
                "monitor",
                f"evento_sonado:{nodo}:{oracion_num}:{nota_raw}:{intensidad_raw}"
            )

        self._exportar_mid(eventos, nodo)
        self._enviar_privado("monitor", f"fin_procesamiento:{nodo}")
        print(f"[{self.nombre}] Procesamiento completo.")

    def _exportar_mid(self, eventos, nodo):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ruta_salida = os.path.join(base, "salida", f"{nodo}.mid")
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        midi = MidiFile()
        track = MidiTrack()
        midi.tracks.append(track)
        for e in eventos:
            track.append(Message("note_on",  note=int(e["nota_midi"]), velocity=max(1, int(e["intensidad_midi"])), time=0))
            track.append(Message("note_off", note=int(e["nota_midi"]), velocity=0, time=240))
        midi.save(ruta_salida)
        print(f"[{self.nombre}] Archivo MIDI exportado → {ruta_salida}")

    def ejecutar(self):
        self._conectar()

        t = threading.Thread(target=self._hilo_escucha, daemon=True)
        t.start()

        print(f"[{self.nombre}] Esperando configuración del Monitor...")

        while True:
            try:
                linea = self.cola.get(timeout=600)
            except queue.Empty:
                print(f"[{self.nombre}] Tiempo de espera agotado.")
                break

            if linea is None:
                break

            m = re.match(r"^DE (\S+): (.+)$", linea)
            if not m:
                print(f"[{self.nombre}] Mensaje: {linea}")
                continue

            remitente, mensaje = m.group(1), m.group(2)

            if mensaje.startswith("config:"):
                # config:<archivo>:<gm>  — gm es opcional, default 0
                partes = mensaje[7:].split(":")
                nombre_archivo = partes[0].strip()
                try:
                    instrumento = int(partes[1]) if len(partes) > 1 else 0
                except (ValueError, IndexError):
                    instrumento = 0

                ruta = os.path.join(self.ruta_textos, nombre_archivo)

                if not os.path.isfile(ruta):
                    print(f"[{self.nombre}] Archivo no encontrado: {ruta}")
                    self._enviar_privado("monitor", f"ERROR: archivo '{nombre_archivo}' no encontrado")
                    continue

                print(f"[{self.nombre}] Config de {remitente}: archivo='{nombre_archivo}' instrumento={instrumento}")

                threading.Thread(
                    target=self._procesar_archivo,
                    args=(ruta, instrumento),
                    daemon=True,
                ).start()

            else:
                print(f"[{self.nombre}] DE {remitente}: {mensaje}")

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _procesar_archivo(self, ruta, instrumento=0):
        """
        Analiza el texto inmediatamente y lanza la reproducción en un hilo
        daemon separado con jitter aleatorio (0–0.5 s) para simular
        procesamiento distribuido asíncrono real.
        """
        try:
            eventos, nodo = self.procesar_texto(ruta)

            def _sonar():
                jitter = random.uniform(0, 0.5)
                if jitter > 0:
                    print(f"[{self.nombre}] Jitter de {jitter:.2f}s antes de reproducción...")
                    time.sleep(jitter)
                self.sonar_texto(eventos, nodo, instrumento)

            threading.Thread(target=_sonar, daemon=True).start()

        except Exception as e:
            print(f"[{self.nombre}] Error al procesar: {e}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 procesador.py <nombre>")
        print("Ej:  python3 procesador.py procesador1")
        sys.exit(1)

    nombre = sys.argv[1]
    host = os.getenv("HOST_SERVIDOR", HOST).strip() or HOST
    puerto = int(os.getenv("PUERTO_SERVIDOR", str(PUERTO)))
    Procesador(nombre=nombre, host=host, puerto=puerto).ejecutar()


if __name__ == "__main__":
    main()
