"""
Servidor TCP central: recibe eventos JSON por socket, registra y genera MIDI.
"""

import os
import re
import socket
import threading

from mido import Message, MidiFile, MidiTrack

from registro import RegistroCorrida


HOST = "127.0.0.1"
PUERTO = 5000
BUFFER = 4096


class ServidorMidiSockets:
    def __init__(self, host=HOST, puerto=PUERTO):
        self.host = host
        self.puerto = puerto
        self.lock = threading.Lock()
        self.en_ejecucion = False

        base = os.path.dirname(os.path.dirname(__file__))
        self.ruta_salida = os.path.join(base, "salida")
        os.makedirs(self.ruta_salida, exist_ok=True)

        self.registro = RegistroCorrida(os.path.join(self.ruta_salida, "log_corrida.txt"))
        self.eventos_por_nodo = {"quijote": [], "mio_cid": []}
        self.sock = None

    def _desescapar(self, texto):
        return (
            texto.replace(r"\\", "\\")
            .replace(r'\"', '"')
            .replace(r"\n", "\n")
            .replace(r"\t", "\t")
        )

    def _campo_texto(self, mensaje, campo):
        m = re.search(rf'"{campo}"\s*:\s*"((?:\\.|[^"\\])*)"', mensaje)
        if not m:
            raise ValueError(f"Falta campo {campo}")
        return self._desescapar(m.group(1))

    def _campo_entero(self, mensaje, campo):
        m = re.search(rf'"{campo}"\s*:\s*(-?\d+)', mensaje)
        if not m:
            raise ValueError(f"Falta campo {campo}")
        return int(m.group(1))

    def _parsear_evento(self, mensaje):
        msg = mensaje.strip()
        if not (msg.startswith("{") and msg.endswith("}")):
            raise ValueError("JSON inválido")

        evento = {
            "nodo": self._campo_texto(msg, "nodo"),
            "oracion_num": self._campo_entero(msg, "oracion_num"),
            "pitch": self._campo_entero(msg, "pitch"),
            "velocity": self._campo_entero(msg, "velocity"),
            "texto_original": self._campo_texto(msg, "texto_original"),
        }
        self._validar(evento)
        return evento

    def _validar(self, evento):
        if evento["nodo"] not in self.eventos_por_nodo:
            raise ValueError("nodo no permitido")
        if evento["oracion_num"] < 1:
            raise ValueError("oracion_num inválido")
        if not (0 <= evento["pitch"] <= 127):
            raise ValueError("pitch fuera de rango")
        if not (0 <= evento["velocity"] <= 127):
            raise ValueError("velocity fuera de rango")

    def _respuesta(self, estado, detalle=""):
        if detalle:
            detalle = detalle.replace("\\", r"\\").replace('"', r'\"')
            return f'{{"estado": "{estado}", "detalle": "{detalle}"}}\n'
        return f'{{"estado": "{estado}"}}\n'

    def _exportar_midi_nodo(self, nodo):
        eventos = self.eventos_por_nodo.get(nodo, [])
        if not eventos:
            return
        midi = MidiFile()
        track = MidiTrack()
        midi.tracks.append(track)
        for e in eventos:
            track.append(Message("note_on", note=int(e["pitch"]), velocity=int(e["velocity"]), time=0))
            track.append(Message("note_off", note=int(e["pitch"]), velocity=0, time=240))
        midi.save(os.path.join(self.ruta_salida, f"{nodo}.mid"))

    def _atender_cliente(self, conexion, direccion):
        self.registro.registrar_info(f"Cliente conectado {direccion[0]}:{direccion[1]}")
        buffer = ""
        try:
            while True:
                data = conexion.recv(BUFFER)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    if not linea.strip():
                        continue
                    try:
                        evento = self._parsear_evento(linea)
                        with self.lock:
                            self.eventos_por_nodo[evento["nodo"]].append(evento)
                            self.registro.registrar_evento(evento)
                            self._exportar_midi_nodo(evento["nodo"])
                        conexion.sendall(self._respuesta("ok").encode("utf-8"))
                    except Exception as e:
                        self.registro.registrar_error(str(e))
                        conexion.sendall(self._respuesta("error", str(e)).encode("utf-8"))
        finally:
            conexion.close()
            self.registro.registrar_info(f"Cliente desconectado {direccion[0]}:{direccion[1]}")

    def iniciar(self):
        self.registro.iniciar()
        self.registro.registrar_info(f"Servidor escuchando en {self.host}:{self.puerto}")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.puerto))
        self.sock.listen(10)
        self.en_ejecucion = True
        print(f"Servidor activo en {self.host}:{self.puerto}")

        try:
            while self.en_ejecucion:
                conn, addr = self.sock.accept()
                threading.Thread(target=self._atender_cliente, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\nCerrando servidor...")
        finally:
            self.detener()

    def detener(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        with self.lock:
            self._exportar_midi_nodo("quijote")
            self._exportar_midi_nodo("mio_cid")
        self.registro.registrar_info("Servidor detenido")
        self.registro.cerrar()
        print("Servidor detenido.")


def main():
    ServidorMidiSockets().iniciar()


if __name__ == "__main__":
    main()
