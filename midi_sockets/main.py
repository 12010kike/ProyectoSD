"""
Punto de entrada único del proyecto MIDI-Sockets.
Todo corre en la misma terminal (compatible con VS Code Terminal integrada).
"""

import os
import platform
import socket as _socket
import subprocess
import sys
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))

_procesos = []
_W = 62  # ancho de los separadores visuales


# ── helpers visuales ────────────────────────────────────────────────

def _limpiar():
    """Limpia la pantalla de forma portable."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def _hr(titulo=""):
    """Línea horizontal con título opcional centrado."""
    if titulo:
        titulo = f"  {titulo}  "
        lado = max(0, (_W - len(titulo)) // 2)
        print("═" * lado + titulo + "═" * max(0, _W - lado - len(titulo)))
    else:
        print("═" * _W)


def _bloque_inicio(nombre):
    """Cabecera visual al arrancar un componente."""
    print()
    _hr(nombre)


def _bloque_fin(nombre):
    """Pie visual cuando un componente termina o se sale de su modo."""
    _hr(f"{nombre} — fin")
    print()


# ── gestión de subprocesos ───────────────────────────────────────────

def _lanzar_con_prefijo(cmd, prefijo, stdin=None):
    """
    Lanza cmd como subproceso en segundo plano.
    Un hilo daemon reenvía su stdout línea a línea con [PREFIJO].
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=stdin,
        cwd=BASE,
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _procesos.append(proc)

    def _leer():
        tag = f"[{prefijo}] "
        try:
            for linea in proc.stdout:
                print(tag + linea, end="", flush=True)
        except Exception:
            pass

    threading.Thread(target=_leer, daemon=True).start()
    return proc


def _servidor_activo(host="127.0.0.1", puerto=5000):
    try:
        with _socket.create_connection((host, puerto), timeout=1):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _cmd_python():
    return sys.executable


# ── opciones del menú ────────────────────────────────────────────────

def _iniciar_servidor():
    _bloque_inicio("SERVIDOR")
    _lanzar_con_prefijo(
        [_cmd_python(), os.path.join(BASE, "servidor", "servidor.py")],
        "SERVIDOR",
    )
    for _ in range(6):
        time.sleep(0.5)
        if _servidor_activo():
            print("[SERVIDOR] Activo en 127.0.0.1:5000 ✓")
            break
    else:
        print("[SERVIDOR] No respondió en 3 s — revisa el log si hay errores.")
    print()
    print("  Siguiente paso: abre los procesadores en terminales separadas y luego")
    print("  usa la opción 2 para lanzar el monitor.")
    print()


def _iniciar_monitor():
    if not _servidor_activo():
        print("  El servidor no está activo. Usa la opción 1 primero.")
        return

    print()
    print("  ANTES DE CONTINUAR:")
    print("    Abre una terminal nueva por cada procesador y ejecuta:")
    print("      python3 cliente/procesador.py procesador1")
    print("      python3 cliente/procesador.py procesador2")
    print("    Espera a que cada uno imprima 'Esperando configuración...'")
    print("    y luego vuelve aquí.")
    try:
        input("\n  Presiona Enter cuando los procesadores estén listos... ")
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelado.")
        return

    _limpiar()
    _bloque_inicio("MONITOR — MODO INTERACTIVO")
    print("  Escribe el comando de configuración y pulsa Enter.")
    print("  Ejemplo:  config(quijote.txt mio_cid.txt, procesador1 procesador2, 40 73)")
    print("  Escribe 'salir' para cerrar el monitor y volver al menú.")
    _hr()
    print()

    # stdin=None: el monitor hereda el teclado de esta terminal para input()
    proc = subprocess.Popen(
        [_cmd_python(), os.path.join(BASE, "cliente", "monitor.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=None,
        cwd=BASE,
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _procesos.append(proc)

    def _leer():
        try:
            for linea in proc.stdout:
                print("[MONITOR] " + linea, end="", flush=True)
        except Exception:
            pass

    threading.Thread(target=_leer, daemon=True).start()
    proc.wait()

    _bloque_fin("MONITOR")
    input("Presiona Enter para volver al menú...")


def _ver_log():
    ruta = os.path.join(BASE, "salida", "log_corrida.txt")
    if not os.path.isfile(ruta):
        print("  No existe log_corrida.txt todavía.")
        return
    _limpiar()
    _bloque_inicio(f"LOG — {ruta}")
    with open(ruta, "r", encoding="utf-8") as f:
        print(f.read())
    _hr()


def _detener_todo():
    _hr("DETENIENDO TODO")
    for proc in _procesos:
        try:
            proc.terminate()
        except Exception:
            pass
    # 2 s de gracia antes de forzar kill
    tiempo_limite = time.time() + 2
    for proc in _procesos:
        restante = max(0, tiempo_limite - time.time())
        try:
            proc.wait(timeout=restante)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
    _procesos.clear()
    print("  Todos los subprocesos detenidos.")
    _hr()


# ── menú ─────────────────────────────────────────────────────────────

def _mostrar_menu():
    _hr("MIDI-SOCKETS")
    activos = sum(1 for p in _procesos if p.poll() is None)
    if activos:
        print(f"  Subprocesos activos: {activos}")
    print()
    print("  1)  Iniciar Servidor")
    print("  2)  Iniciar Monitor  (abre procesadores primero en otras terminales)")
    print("  3)  Ver log de corrida")
    print("  4)  Detener todo y salir")
    _hr()


def main():
    os.chdir(BASE)

    while True:
        _mostrar_menu()
        try:
            opcion = input("  Selecciona [1-4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo de MIDI-SOCKETS.")
            _detener_todo()
            break

        if opcion == "1":
            _iniciar_servidor()
        elif opcion == "2":
            _iniciar_monitor()
        elif opcion == "3":
            _ver_log()
            input("\nPresiona Enter para volver al menú...")
        elif opcion == "4":
            _detener_todo()
            print("  Saliendo de MIDI-SOCKETS.")
            break
        else:
            print("  Opción inválida.")


if __name__ == "__main__":
    main()
