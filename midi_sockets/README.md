# MIDI-Sockets: Sincronización de Estructuras Literarias

Sistema distribuido en Python que analiza métricas lingüísticas de textos literarios españoles (El Quijote, El Cantar de Mío Cid) y los convierte en eventos MIDI reproducibles, usando una arquitectura servidor-monitor-procesador sobre TCP.

## Qué hace

1. El **servidor** TCP gestiona la mensajería entre nodos (monitor y procesadores).
2. El **monitor** (orquestador) envía configuración a los procesadores y recopila resultados.
3. Cada **procesador** (worker) carga un corpus, lo analiza y reproduce los eventos MIDI con FluidSynth.
4. Por cada oración del texto se calcula:
   - `metrica_base = promedio(len(palabra) × suma_ascii(palabra))`
   - `densidad_lexica = (palabras_unicas / total) × promedio_longitud`
   - `valor_bruto = metrica_base × (1 + densidad_lexica)`
5. Los valores se normalizan a `[0, 127]` para obtener `nota_midi` y `intensidad_midi`.
6. El monitor genera el análisis comparativo al finalizar todos los procesadores, usando `avg` y `std` de notas e intensidades por obra.
7. Cada procesador exporta un archivo `.mid` en `salida/`.

## Instalación de dependencias Python

```bash
cd midi_sockets
pip install -r requisitos.txt
```

## Instalación de dependencias del sistema

FluidSynth debe estar instalado en el sistema operativo antes de ejecutar el proyecto.

**macOS (Homebrew):**
```bash
brew install fluid-synth
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install fluidsynth
```

**Windows:**
Descarga el instalador desde https://www.fluidsynth.org y agrégalo al PATH del sistema.

## Descarga del SoundFont

El archivo `FluidR3_GM.sf2` (~142 MB) no está incluido en el repositorio. Descárgalo desde:
- https://member.keymusician.com/Member/FluidR3_GM/index.html
- o busca "FluidR3_GM.sf2" en musescore.org

Colócalo en:
```
midi_sockets/soundfonts/FluidR3_GM.sf2
```

## Ejecución

Usa el menú interactivo de `main.py`. Abre **4 terminales** en el directorio `midi_sockets/`:

**Terminal 1 — Servidor:**
```bash
python3 main.py
# Selecciona opción 1: Iniciar servidor
```

**Terminal 2 — Monitor (orquestador):**
```bash
python3 main.py
# Selecciona opción 2: Iniciar monitor
```

**Terminales 3 y 4 — Procesadores (uno por corpus):**
```bash
python3 main.py
# Selecciona opción 3: Iniciar procesador
# Nombre sugerido: procesador1 (Terminal 3), procesador2 (Terminal 4)
```

**En la Terminal del Monitor**, una vez que todos los procesadores estén conectados, escribe el comando de configuración:

```
config(quijote.txt mio_cid.txt, procesador1 procesador2)
```

Con instrumento GM personalizado (opcional):
```
config(quijote.txt mio_cid.txt, procesador1 procesador2, 40 73)
```

Instrumentos GM disponibles: `0` Piano | `11` Vibraphone | `19` Organ | `24` Guitar | `40` Violin | `42` Cello | `56` Trumpet | `73` Flute

Escribe `salir` para cerrar el monitor.

## Artefactos generados

| Archivo | Descripción |
|---------|-------------|
| `salida/log_corrida.txt` | Log completo de la corrida con análisis comparativo |
| `salida/quijote.mid` | Archivo MIDI generado del Quijote |
| `salida/mio_cid.mid` | Archivo MIDI generado del Cantar de Mío Cid |

## Variables de entorno opcionales

Los nodos monitor y procesador aceptan estas variables para sobrescribir la configuración por defecto (host `127.0.0.1`, puerto `5000`):

| Variable | Default | Ejemplo |
|----------|---------|---------|
| `HOST_SERVIDOR` | `127.0.0.1` | `192.168.1.10` |
| `PUERTO_SERVIDOR` | `5000` | `6000` |

Ejemplo de uso:
```bash
HOST_SERVIDOR=192.168.1.10 PUERTO_SERVIDOR=6000 python3 cliente/monitor.py
HOST_SERVIDOR=192.168.1.10 PUERTO_SERVIDOR=6000 python3 cliente/procesador.py procesador1
```

## Estructura del proyecto

```
midi_sockets/
├── main.py               ← Punto de entrada: menú interactivo
├── requisitos.txt        ← Dependencias pip
├── cliente/
│   ├── monitor.py        ← Orquestador: distribuye trabajo y genera análisis comparativo
│   ├── procesador.py     ← Worker: analiza texto, reproduce MIDI y exporta .mid
│   └── analizador.py     ← Motor de análisis: convierte texto en eventos MIDI
├── servidor/
│   └── servidor.py       ← Servidor TCP con soporte de mensajes privados
├── texto/
│   ├── quijote.txt       ← Corpus 1: fragmento del Quijote
│   └── mio_cid.txt       ← Corpus 2: fragmento del Cantar de Mío Cid
├── salida/               ← Artefactos generados (log, .mid)
└── soundfonts/
    └── FluidR3_GM.sf2    ← SoundFont GM (descarga manual, ~142 MB)
```
