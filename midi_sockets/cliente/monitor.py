"""
Monitor (Orquestador): distribuye trabajo, recibe eventos y genera análisis comparativo.

Uso:
    python3 cliente/monitor.py

Formato de comando:
    config(quijote.txt mio_cid.txt, procesador1 procesador2)
    config(quijote.txt mio_cid.txt, procesador1 procesador2, 40 73)
"""

import math
import os
import re
import socket
import threading
import time
from collections import Counter

HOST = "127.0.0.1"
PUERTO = 5000
BUFFER = 4096
NOMBRE = "monitor"

_NOMBRES_GM = {
    0:  "Piano",
    11: "Vibraphone",
    19: "Organ",
    24: "Guitar",
    40: "Violin",
    42: "Cello",
    56: "Trumpet",
    73: "Flute",
}

_TABLA_GM = (
    "Instrumentos GM disponibles: "
    "0 Piano | 11 Vibraphone | 19 Organ | 24 Guitar | "
    "40 Violin | 42 Cello | 56 Trumpet | 73 Flute"
)


def _nombre_gm(num):
    return _NOMBRES_GM.get(int(num), f"GM#{num}")


def _avg(lst):
    return sum(lst) / len(lst) if lst else 0.0


def _std(lst):
    if len(lst) < 2:
        return 0.0
    m = _avg(lst)
    return math.sqrt(sum((x - m) ** 2 for x in lst) / len(lst))


def _entropia(valores):
    """Entropía de Shannon en bits sobre la distribución de valores."""
    n = len(valores)
    if n == 0:
        return 0.0
    counts = Counter(valores)
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c > 0)


def _iqr(valores):
    """Rango intercuartílico (P75 - P25)."""
    if len(valores) < 4:
        return 0.0
    s = sorted(valores)
    n = len(s)
    return s[3 * n // 4] - s[n // 4]


def _contorno(valores):
    """
    Contorno melódico: (subidas, bajadas, repetidas) como porcentajes.
    Retorna tupla (pct_sube, pct_baja, pct_igual).
    """
    if len(valores) < 2:
        return (0.0, 0.0, 0.0)
    pares = list(zip(valores, valores[1:]))
    total = len(pares)
    sube  = sum(1 for a, b in pares if b > a)
    baja  = sum(1 for a, b in pares if b < a)
    igual = sum(1 for a, b in pares if b == a)
    return (sube / total * 100, baja / total * 100, igual / total * 100)


class Monitor:
    def __init__(self, host=HOST, puerto=PUERTO):
        self.host = host
        self.puerto = puerto
        self.sock = None
        self._buffer = ""
        self.lock_send = threading.Lock()
        self.lock_datos = threading.Lock()

        self.eventos_por_nodo = {}   # {nodo: [{"nota_midi": ..., "intensidad_midi": ...}]}
        self.nodos_esperados = set()
        self.nodos_completados = set()
        self._analisis_ejecutado = False
        self._lock_analisis = threading.Lock()
        self.instrumento_por_nodo = {}  # {nodo: gm}  — populado al enviar config
        self._timer_timeout = None

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ruta_log = os.path.join(base, "salida", "log_corrida.txt")
        self._iniciar_log()

    def _iniciar_log(self):
        os.makedirs(os.path.dirname(self.ruta_log), exist_ok=True)
        with open(self.ruta_log, "w", encoding="utf-8") as f:
            f.write("=== INICIO DE CORRIDA DISTRIBUIDA ===\n")
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=====================================\n")

    def _conectar(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.puerto))
        self._enviar_raw(f"IDENT {NOMBRE}")
        resp = self._leer_linea_directa()
        if resp != "OK":
            raise ConnectionError(f"Servidor rechazó identificación: {resp}")
        print(f"[monitor] Conectado al servidor como '{NOMBRE}'")

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
        self._enviar_raw(f"/w {destino} {mensaje}")

    def _hilo_escucha(self):
        buf = self._buffer
        try:
            while True:
                data = self.sock.recv(BUFFER)
                if not data:
                    print("[monitor] Servidor cerró la conexión.")
                    break
                buf += data.decode("utf-8", errors="replace")
                while "\n" in buf:
                    linea, buf = buf.split("\n", 1)
                    linea = linea.strip()
                    if linea:
                        self._procesar_entrante(linea)
        except Exception as e:
            print(f"[monitor] Error en escucha: {e}")

    def _escribir_log(self, linea):
        try:
            with open(self.ruta_log, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except Exception:
            pass

    def _procesar_entrante(self, linea):
        m = re.match(r"^DE (\S+): (.+)$", linea)
        if not m:
            print(f"[monitor] {linea}")
            return

        remitente, mensaje = m.group(1), m.group(2)

        if mensaje.startswith("evento_sonado:"):
            partes = mensaje.split(":")
            if len(partes) == 5:
                _, nodo, oracion, nota, intensidad = partes
                ts = time.strftime("%H:%M:%S")
                with self.lock_datos:
                    gm = self.instrumento_por_nodo.get(nodo, 0)
                instr_nombre = _nombre_gm(gm)
                linea_evento = (
                    f"[{ts}] evento_sonado | nodo={nodo} | oracion={oracion} "
                    f"| nota={nota} | intensidad={intensidad} | instr={instr_nombre}"
                )
                print(linea_evento)
                self._escribir_log(linea_evento)
                with self.lock_datos:
                    if nodo not in self.eventos_por_nodo:
                        self.eventos_por_nodo[nodo] = []
                    self.eventos_por_nodo[nodo].append({
                        "nota_midi": int(nota),
                        "intensidad_midi": int(intensidad),
                    })
            else:
                print(f"[monitor] evento_sonado malformado de {remitente}: {mensaje}")

        elif mensaje.startswith("fin_procesamiento:"):
            nodo = mensaje.split(":", 1)[1].strip()
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] [monitor] Procesador '{remitente}' terminó (nodo={nodo})")
            with self.lock_datos:
                self.nodos_completados.add(nodo)
                completados = set(self.nodos_completados)
                esperados = set(self.nodos_esperados)

            ejecutar = False
            if esperados and completados >= esperados:
                with self._lock_analisis:
                    if not self._analisis_ejecutado:
                        self._analisis_ejecutado = True
                        ejecutar = True

            if ejecutar:
                if self._timer_timeout:
                    self._timer_timeout.cancel()
                self._analisis_comparativo()

        else:
            print(f"[monitor] DE {remitente}: {mensaje}")

    def _timeout_cb(self):
        """Fuerza el análisis comparativo si transcurren 60 s sin fin_procesamiento de todos los nodos."""
        ejecutar = False
        with self._lock_analisis:
            if not self._analisis_ejecutado:
                self._analisis_ejecutado = True
                ejecutar = True
        if ejecutar:
            with self.lock_datos:
                pendientes = self.nodos_esperados - self.nodos_completados
            print(f"[monitor] Timeout 60 s: forzando análisis. Nodos sin respuesta: {pendientes}")
            self._analisis_comparativo()

    def _analisis_comparativo(self):
        with self.lock_datos:
            snapshot = {n: list(evs) for n, evs in self.eventos_por_nodo.items()}
            instrs = dict(self.instrumento_por_nodo)

        lineas = []
        lineas.append("\n=== ANÁLISIS COMPARATIVO DE FIRMA SONORA ===")
        encabezado = (
            f"{'Obra':<18}| {'nota_midi avg':>13} | {'nota_midi std':>13} "
            f"| {'intensidad avg':>14} | {'intensidad std':>14}"
        )
        lineas.append(encabezado)
        lineas.append("-" * len(encabezado))

        stats = {}
        for nodo, evs in sorted(snapshot.items()):
            if not evs:
                continue
            notas = [e["nota_midi"] for e in evs]
            ints = [e["intensidad_midi"] for e in evs]
            nota_avg, nota_std = _avg(notas), _std(notas)
            int_avg, int_std = _avg(ints), _std(ints)

            ent   = _entropia(notas)
            iqr   = _iqr(notas)
            pct_s, pct_b, pct_i = _contorno(notas)

            gm = instrs.get(nodo, 0)
            stats[nodo] = {
                "nota_avg": nota_avg, "nota_std": nota_std,
                "int_avg": int_avg,   "int_std": int_std,
                "entropia": ent,      "iqr": iqr,
                "pct_sube": pct_s,    "pct_baja": pct_b, "pct_igual": pct_i,
                "gm": gm,             "n_eventos": len(evs),
            }
            instr_nombre = _nombre_gm(gm)
            lineas.append(
                f"{nodo:<18}| {nota_avg:>13.1f} | {nota_std:>13.1f} "
                f"| {int_avg:>14.1f} | {int_std:>14.1f}  [{instr_nombre}]"
            )

        lineas.append("")
        lineas.append("=== MÉTRICAS AVANZADAS ===")
        enc_av = (
            f"{'Obra':<18}| {'Entropía(bits)':>14} | {'IQR notas':>9} "
            f"| {'Subidas%':>8} | {'Bajadas%':>8} | {'Repetidas%':>10} | {'N eventos':>9}"
        )
        lineas.append(enc_av)
        lineas.append("-" * len(enc_av))
        for nodo, s in sorted(stats.items()):
            lineas.append(
                f"{nodo:<18}| {s['entropia']:>14.3f} | {s['iqr']:>9.1f} "
                f"| {s['pct_sube']:>7.1f}% | {s['pct_baja']:>7.1f}% "
                f"| {s['pct_igual']:>9.1f}% | {s['n_eventos']:>9}"
            )

        if len(stats) == 2:
            nodos = list(stats.keys())
            n0, n1 = nodos[0], nodos[1]
            if stats[n0]["nota_std"] >= stats[n1]["nota_std"]:
                mayor, menor = n0, n1
            else:
                mayor, menor = n1, n0
            ent_mayor = "mayor" if stats[mayor]["entropia"] >= stats[menor]["entropia"] else "menor"

            lineas.append("")
            lineas.append(
                f"CONCLUSIÓN: '{mayor}' presenta mayor variedad rítmica "
                f"(std={stats[mayor]['nota_std']:.1f} vs {stats[menor]['nota_std']:.1f}), "
                f"entropía {ent_mayor} ({stats[mayor]['entropia']:.2f} vs "
                f"{stats[menor]['entropia']:.2f} bits), "
                f"IQR={stats[mayor]['iqr']:.0f} vs {stats[menor]['iqr']:.0f}. "
                f"Contorno de '{mayor}': "
                f"{stats[mayor]['pct_sube']:.0f}% ↑ / "
                f"{stats[mayor]['pct_baja']:.0f}% ↓ / "
                f"{stats[mayor]['pct_igual']:.0f}% =. "
                f"'{menor}' muestra cadencia más uniforme "
                f"(std={stats[menor]['nota_std']:.1f}), propio de su género."
            )

        texto_analisis = "\n".join(lineas)
        print(texto_analisis)

        try:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self.ruta_log, "a", encoding="utf-8") as f:
                f.write(texto_analisis + "\n")
                f.write("=====================================\n")
                f.write(f"Fin: {ts}\n")
                f.write("=== FIN DE CORRIDA DISTRIBUIDA ===\n")
            print(f"\n[monitor] Análisis guardado en {self.ruta_log}")
        except Exception as e:
            print(f"[monitor] No se pudo guardar el log: {e}")

    def _parsear_config(self, entrada):
        """
        Formatos aceptados:
          config(arch1 arch2, proc1 proc2)
          config(arch1 arch2, proc1 proc2, gm1 gm2)
        Retorna [(proc, archivo, gm), ...] o None si error.
        """
        m = re.match(
            r"config\((.+?),\s*(.+?)(?:,\s*(.+?))?\)\s*$",
            entrada.strip(),
        )
        if not m:
            return None

        archivos     = m.group(1).strip().split()
        procesadores = m.group(2).strip().split()
        gms_raw      = m.group(3).strip().split() if m.group(3) else []

        if len(archivos) != len(procesadores):
            print("[monitor] Número de archivos y procesadores no coincide.")
            return None

        if gms_raw:
            if len(gms_raw) != len(archivos):
                print("[monitor] Número de instrumentos debe coincidir con el de archivos (o se omite para usar 0).")
                return None
            try:
                gms = [int(g) for g in gms_raw]
            except ValueError:
                print("[monitor] Los instrumentos deben ser números enteros 0-127.")
                return None
            for g in gms:
                if not 0 <= g <= 127:
                    print(f"[monitor] Instrumento GM fuera de rango [0,127]: {g}")
                    return None
        else:
            gms = [0] * len(archivos)

        return list(zip(procesadores, archivos, gms))

    def ejecutar(self):
        self._conectar()

        t = threading.Thread(target=self._hilo_escucha, daemon=True)
        t.start()

        print("\n" + _TABLA_GM)
        print()
        print("[monitor] Esperando comando de configuración.")
        print("  Formato: config(quijote.txt mio_cid.txt, procesador1 procesador2)")
        print("  Con instrumento: config(quijote.txt mio_cid.txt, procesador1 procesador2, 40 73)")
        print("  Escribe 'analizar' para forzar análisis, 'salir' para terminar.\n")

        while True:
            try:
                entrada = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[monitor] Cerrando.")
                break

            if entrada.lower() in ("salir", "exit", "quit"):
                break

            if entrada.lower() == "analizar":
                self._analisis_comparativo()
                continue

            if not entrada:
                continue

            asignaciones = self._parsear_config(entrada)
            if asignaciones is None:
                print("[monitor] Formato inválido. Ejemplo:")
                print("  config(quijote.txt mio_cid.txt, procesador1 procesador2)")
                print("  config(quijote.txt mio_cid.txt, procesador1 procesador2, 40 73)")
                continue

            with self.lock_datos:
                self.nodos_esperados.clear()
                self.nodos_completados.clear()
                self.eventos_por_nodo.clear()
                self.instrumento_por_nodo.clear()
                for _, archivo, gm in asignaciones:
                    nodo = os.path.splitext(archivo)[0]
                    self.nodos_esperados.add(nodo)
                    self.instrumento_por_nodo[nodo] = gm
            with self._lock_analisis:
                self._analisis_ejecutado = False

            for procesador, archivo, gm in asignaciones:
                msg = f"config:{archivo}:{gm}"
                instr_nombre = _nombre_gm(gm)
                print(f"[monitor] → /w {procesador} {msg}  ({instr_nombre})")
                self._enviar_privado(procesador, msg)

            print(f"[monitor] Configuración enviada. Esperando {len(asignaciones)} procesador(es)...\n")
            if self._timer_timeout:
                self._timer_timeout.cancel()
            self._timer_timeout = threading.Timer(60.0, self._timeout_cb)
            self._timer_timeout.daemon = True
            self._timer_timeout.start()

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass


def main():
    host = os.getenv("HOST_SERVIDOR", HOST).strip() or HOST
    puerto = int(os.getenv("PUERTO_SERVIDOR", str(PUERTO)))
    Monitor(host=host, puerto=puerto).ejecutar()


if __name__ == "__main__":
    main()
