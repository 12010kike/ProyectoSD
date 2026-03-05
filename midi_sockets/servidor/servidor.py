"""
Servidor TCP minimalista: gestión de conexiones y mensajería privada.
No contiene lógica de negocio, MIDI ni análisis de texto.
"""

import socket
import threading

HOST = "127.0.0.1"
PUERTO = 5000
BUFFER = 4096


class ServidorMensajeria:
    def __init__(self, host=HOST, puerto=PUERTO):
        self.host = host
        self.puerto = puerto
        self.clientes = {}          # nombre -> socket
        self.lock = threading.Lock()
        self.sock = None

    # ------------------------------------------------------------------ envío

    def _enviar(self, conexion, mensaje):
        try:
            conexion.sendall((mensaje + "\n").encode("utf-8"))
        except Exception:
            pass

    def _broadcast(self, remitente, mensaje):
        linea = f"DE {remitente}: {mensaje}"
        with self.lock:
            destinos = [(n, c) for n, c in self.clientes.items() if n != remitente]
        for _, conn in destinos:
            self._enviar(conn, linea)

    def _privado(self, remitente, destino, mensaje, conn_remitente):
        with self.lock:
            conn_dest = self.clientes.get(destino)
        if conn_dest is None:
            self._enviar(conn_remitente, f"ERROR: {destino} no conectado")
            return
        self._enviar(conn_dest, f"DE {remitente}: {mensaje}")

    # --------------------------------------------------------- hilo por cliente

    def _atender_cliente(self, conexion, direccion):
        nombre = None
        buffer = ""
        try:
            # Fase 1: identificación
            while "\n" not in buffer:
                data = conexion.recv(BUFFER)
                if not data:
                    return
                buffer += data.decode("utf-8", errors="replace")

            linea, buffer = buffer.split("\n", 1)
            linea = linea.strip()

            if not linea.startswith("IDENT "):
                self._enviar(conexion, "ERROR: se esperaba IDENT <nombre>")
                return

            nombre = linea[6:].strip()
            if not nombre:
                self._enviar(conexion, "ERROR: nombre vacío")
                return

            with self.lock:
                if nombre in self.clientes:
                    self._enviar(conexion, f"ERROR: nombre '{nombre}' ya en uso")
                    return
                self.clientes[nombre] = conexion

            self._enviar(conexion, "OK")
            print(f"[+] {nombre} conectado desde {direccion[0]}:{direccion[1]}")

            # Fase 2: mensajes
            while True:
                while "\n" not in buffer:
                    data = conexion.recv(BUFFER)
                    if not data:
                        return
                    buffer += data.decode("utf-8", errors="replace")

                linea, buffer = buffer.split("\n", 1)
                linea = linea.strip()
                if not linea:
                    continue

                if linea.startswith("/w "):
                    # /w <destino> <mensaje>
                    partes = linea[3:].split(" ", 1)
                    if len(partes) < 2:
                        self._enviar(conexion, "ERROR: uso: /w <destino> <mensaje>")
                        continue
                    destino, msg = partes[0], partes[1]
                    self._privado(nombre, destino, msg, conexion)
                else:
                    self._broadcast(nombre, linea)

        except Exception as e:
            print(f"[!] Error con {nombre or direccion}: {e}")
        finally:
            if nombre:
                with self.lock:
                    self.clientes.pop(nombre, None)
                print(f"[-] {nombre} desconectado")
            try:
                conexion.close()
            except Exception:
                pass

    # --------------------------------------------------------------- arranque

    def iniciar(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.puerto))
        self.sock.listen(10)
        print(f"Servidor activo en {self.host}:{self.puerto}  (Ctrl+C para salir)")
        try:
            while True:
                conn, addr = self.sock.accept()
                threading.Thread(
                    target=self._atender_cliente, args=(conn, addr), daemon=True
                ).start()
        except KeyboardInterrupt:
            print("\nCerrando servidor...")
        finally:
            if self.sock:
                self.sock.close()


def main():
    ServidorMensajeria().iniciar()


if __name__ == "__main__":
    main()
