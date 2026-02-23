"""
Punto de entrada principal del proyecto MIDI-Sockets.

Menú simplificado:
- Cliente con menú interactivo
"""

import os


def limpiar_pantalla():
    os.system("clear")


def ejecutar_cliente():
    print("\nIniciando cliente con menú interactivo...\n")
    os.system("python3 cliente/cliente.py")


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
