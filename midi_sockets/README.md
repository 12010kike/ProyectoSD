# MIDI-Sockets: Sincronización de Estructuras Literarias

Sistema distribuido en Python para analizar texto literario y convertirlo en eventos MIDI enviados por sockets TCP.

## Qué hace
1. Cada cliente carga un corpus (`quijote` o `mio_cid`).
2. Tokeniza por oraciones y palabras.
3. Calcula por oración:
   - `valor_bruto = promedio(len(palabra) * suma_ascii(palabra))`
4. Normaliza:
   - `pitch` a `[0,127]` con `f(x) = ((x-x_min)/(x_max-x_min))*127`
   - `velocity` según cantidad de palabras, también a `[0,127]`.
5. Envía eventos JSON al servidor por TCP.
6. El servidor registra todo en `salida/log_corrida.txt` y genera:
   - `salida/quijote.mid`
   - `salida/mio_cid.mid`

## Dependencias
```bash
pip install -r requisitos.txt
```

## Ejecución
Terminal 1:
```bash
cd midi_sockets
python3 servidor/servidor.py
```

Terminal 2:
```bash
cd midi_sockets
NODO=quijote VISIBILIDAD=1 SONAR_LOCAL=1 python3 cliente/cliente.py
```

Terminal 3:
```bash
cd midi_sockets
NODO=mio_cid VISIBILIDAD=1 SONAR_LOCAL=1 python3 cliente/cliente.py
```

## Visibilidad
Con `VISIBILIDAD=1`, el cliente imprime:
- oraciones tokenizadas
- palabras por oración
- valor bruto
- `pitch` y `velocity`

## Sonido
Con `SONAR_LOCAL=1`, el cliente intenta reproducir los eventos por un puerto MIDI de salida local (`mido`).
Si no hay puerto disponible, se informa por consola y el envío al servidor continúa.
