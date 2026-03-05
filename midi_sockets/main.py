"""
Punto de entrada único del proyecto MIDI-Sockets.
Lanza servidor, monitor y procesadores en terminales independientes.
"""

import os
import platform
import socket as _socket
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))


def _servidor_activo(host="127.0.0.1", puerto=5000):
    try:
        with _socket.create_connection((host, puerto), timeout=1):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _abrir_terminal(script, args=""):
    """Abre el script en una terminal nueva independiente."""
    cmd = f"python3 {script} {args}".strip()
    sistema = platform.system()

    if sistema == "Darwin":
        # macOS: abre en una nueva ventana de Terminal.app
        apple_script = (
            f'tell application "Terminal" to do script '
            f'"cd {BASE} && {cmd}"'
        )
        subprocess.Popen(["osascript", "-e", apple_script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    elif sistema == "Linux":
        # Intenta gnome-terminal, luego xterm como fallback
        for terminal, flag in [
            (["gnome-terminal", "--"], ["bash", "-c", f"cd {BASE} && {cmd}; exec bash"]),
            (["xterm", "-e"], ["bash", "-c", f"cd {BASE} && {cmd}"]),
        ]:
            try:
                subprocess.Popen(terminal + flag)
                return
            except FileNotFoundError:
                continue
        print(f"[!] No se encontró terminal gráfica. Ejecuta manualmente:\n  cd {BASE} && {cmd}")

    elif sistema == "Windows":
        subprocess.Popen(
            ["cmd", "/c", "start", "cmd", "/k", f"cd /d {BASE} && {cmd}"]
        )
    else:
        print(f"Sistema '{sistema}' no soportado. Ejecuta manualmente:\n  cd {BASE} && {cmd}")


def _iniciar_servidor():
    script = os.path.join(BASE, "servidor", "servidor.py")
    print("[main] Iniciando servidor en nueva terminal...")
    _abrir_terminal(script)


def _iniciar_monitor():
    if not _servidor_activo():
        print("  El servidor no está activo. Inicia el servidor primero (opción 1).")
        input("  Presiona Enter para continuar...")
        return
    script = os.path.join(BASE, "cliente", "monitor.py")
    print("[main] Iniciando monitor en nueva terminal...")
    _abrir_terminal(script)


def _iniciar_procesador():
    if not _servidor_activo():
        print("  El servidor no está activo. Inicia el servidor primero (opción 1).")
        input("  Presiona Enter para continuar...")
        return
    nombre = input("  Nombre del procesador (ej: procesador1): ").strip()
    if not nombre:
        print("  Nombre vacío, operación cancelada.")
        return
    script = os.path.join(BASE, "cliente", "procesador.py")
    print(f"[main] Iniciando '{nombre}' en nueva terminal...")
    _abrir_terminal(script, args=nombre)


def _ver_log():
    ruta = os.path.join(BASE, "salida", "log_corrida.txt")
    if not os.path.isfile(ruta):
        print("  No existe log_corrida.txt todavía.")
        return
    print(f"\n{'='*60}")
    print(f"  LOG: {ruta}")
    print(f"{'='*60}")
    with open(ruta, "r", encoding="utf-8") as f:
        print(f.read())
    print(f"{'='*60}")


def mostrar_menu():
    print("\n=== MIDI-SOCKETS | MENÚ PRINCIPAL ===")
    print("  1) Iniciar Servidor")
    print("  2) Iniciar Monitor")
    print("  3) Iniciar Procesador  (repetible para múltiples nodos)")
    print("  4) Ver log de corrida")
    print("  5) Salir")


def main():
    os.chdir(BASE)

    while True:
        mostrar_menu()
        opcion = input("\nSelecciona [1-5]: ").strip()

        if opcion == "1":
            _iniciar_servidor()
        elif opcion == "2":
            _iniciar_monitor()
        elif opcion == "3":
            _iniciar_procesador()
        elif opcion == "4":
            _ver_log()
            input("\nPresiona Enter para volver al menú...")
        elif opcion == "5":
            print("Saliendo de MIDI-SOCKETS.")
            break
        else:
            print("  Opción inválida.")


if __name__ == "__main__":
    main()
