"""
Sistema de logging estructurado para la corrida distribuida.
"""

import os
import time


class RegistroCorrida:
    def __init__(self, ruta_log):
        self.ruta_log = ruta_log
        carpeta = os.path.dirname(self.ruta_log)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)

    def _marca_tiempo(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _escribir(self, linea):
        with open(self.ruta_log, "a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")

    def iniciar(self):
        with open(self.ruta_log, "w", encoding="utf-8") as archivo:
            archivo.write("=== INICIO DE CORRIDA DISTRIBUIDA ===\n")
            archivo.write(f"Fecha: {self._marca_tiempo()}\n")
            archivo.write("=====================================\n")

    def registrar_evento(self, evento):
        self._escribir(
            f"[{self._marca_tiempo()}] EVENTO "
            f"nodo={evento.get('nodo')} "
            f"oracion={evento.get('oracion_num')} "
            f"pitch={evento.get('pitch')} "
            f"velocity={evento.get('velocity')} "
            f"texto=\"{evento.get('texto_original', '')}\""
        )

    def registrar_info(self, mensaje):
        self._escribir(f"[{self._marca_tiempo()}] INFO {mensaje}")

    def registrar_error(self, mensaje):
        self._escribir(f"[{self._marca_tiempo()}] ERROR {mensaje}")

    def cerrar(self):
        self._escribir("=====================================")
        self._escribir(f"Fin: {self._marca_tiempo()}")
        self._escribir("=== FIN DE CORRIDA DISTRIBUIDA ===")
