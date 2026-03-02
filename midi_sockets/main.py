"""
Punto de entrada principal del proyecto MIDI-Sockets.
"""

import os
import sys


def limpiar_pantalla():
    os.system("clear")


def ejecutar_cliente():
    base = os.path.dirname(os.path.abspath(__file__))
    if base not in sys.path:
        sys.path.insert(0, base)
    from cliente.cliente import main as cliente_main
    print("\nIniciando cliente con menú interactivo...\n")
    cliente_main()


def mostrar_menu():
    print("=== MIDI-SOCKETS | MENÚ PRINCIPAL ===")
    print("1) Iniciar cliente")
    print("2) Salir")


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)

    while True:
        limpiar_pantalla()
        mostrar_menu()
        opcion = input("\nSelecciona una opción [1-2]: ").strip()

        if opcion == "1":
            ejecutar_cliente()
            input("\nPresiona Enter para volver al menú...")
        elif opcion == "2":
            print("Saliendo de MIDI-SOCKETS.")
            break
        else:
            print("Opción inválida.")
            input("Presiona Enter para intentar nuevamente...")


if __name__ == "__main__":
    main()
