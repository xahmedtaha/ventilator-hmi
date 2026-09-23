# 05 — Serial Protocol

This is the reference for the firmware team building the real ventilator MCU. The message format
is implemented and unit-tested today (`hmi/device/protocol.py`, `tests/test_protocol.py`) even
though no real MCU exists yet — the Pi side is ready and waiting for it.

## Framing and checksum

**Link:** USB/UART, **115200 baud, 8N1**. Every message is one text line, NMEA-style (the same
style GPS receivers use):

```
$<TYPE>,<field1>,<field2>,...*<CS>\n
```

`CS` is the **XOR of every character between `$` and `*`**, written as two uppercase hex digits.
A line whose checksum does not match is ignored (and counted as a bad line) rather than acted on
— a corrupted "set pressure to 999" is far more dangerous than a dropped sample.

**Fields are ASCII only** (no accents, no '·' or '–'): `protocol.py` raises `ProtocolError` if a
text field contains a non-ASCII character.

### Worked example: encoding `$H,42*..`

The heartbeat message with sequence number 42 has body `H,42` (everything between `$` and `*`).
XOR each character's ASCII code into a running value, starting at 0:

| Step | Character | ASCII (hex) | Running XOR |
|---|---|---|---|
| 1 | `H` | `0x48` | `0x48` |
| 2 | `,` | `0x2C` | `0x48 ^ 0x2C = 0x64` |
| 3 | `4` | `0x34` | `0x64 ^ 0x34 = 0x50` |
| 4 | `2` | `0x32` | `0x50 ^ 0x32 = 0x62` |

The final value `0x62` is written as two uppercase hex digits: `62`. The complete line is:

```
$H,42*62
```

(`\n` terminates the line but is not part of the checksum.)

## MCU → Pi

| Type | Fields | Rate | Example |
|---|---|---|---|
| `D` data sample | t_ms, pressure_cmH2O, flow_Lpm, volume_mL, phase (`I`/`E`) | 50 Hz | `$D,12345,18.2,32.5,410,I*2A` |
| `M` monitor status | fio2_pct, battery_pct, power (`AC`/`BAT`), o2_supply (`OK`/`FAIL`) | 1 Hz | `$M,40.5,87,AC,OK*5B` |
| `R` test result | test (`SELF`/`LEAK`/`COMP`/`CAL`/`ALARM`), `PASS`/`FAIL`, detail text (**no commas**) | on completion | `$R,LEAK,PASS,Leak 45 mL/min (limit < 200)*..` |
| `F` fault | code, `1` active / `0` cleared | on change | `$F,FLOW_SENSOR,1*..` |
| `K` acknowledge | command type, `OK`/`ERR`, reason | per command | `$K,S,OK,*..` |
| `H` heartbeat | sequence number | 5 Hz | `$H,42*62` |

The `R` message's detail text carries no commas by design, since commas are the field separator —
`protocol.py` raises `ProtocolError` if a field ever contains one (or `*`, `$`, or a line break).

## Pi → MCU

| Type | Fields | Example |
|---|---|---|
| `S` set parameter | name (`MODE`,`VT`,`PINSP`,`RR`,`PEEP`,`FIO2`,`TI`,`TRIG`,`PMAX`), value | `$S,VT,500*64` |
| `C` command | `START` / `STANDBY` | `$C,START*..` |
| `X` run test | `SELF` / `LEAK` / `COMP` / `CAL` / `ALARM` | `$X,LEAK*..` |
| `B` buzzer | priority `0` none / `1` low / `2` medium / `3` high, paused `0`/`1` | `$B,3,0*..` |
| `H` heartbeat | sequence number | `$H,17*..` |

`PMAX` is the high-pressure alarm limit — the Pi sends it so the MCU can enforce the pressure
safety cut-off itself, without waiting on the Pi's alarm engine (see
[docs/02-alarms.md](02-alarms.md)).

## Timing

| Message | Rate | Timeout |
|---|---|---|
| `D` data sample | 50 Hz | — |
| `M` monitor status | 1 Hz | — |
| `H` heartbeat, each direction | 5 Hz | Link declared lost after **1 s** of silence |

**What the MCU must do when the Pi's heartbeat stops:** if the MCU has not received a Pi `$H` line
for more than 1 s, it must assume the Pi is frozen or crashed and **sound the high-priority buzzer
pattern on its own**, without waiting to be told. This is the one alarm the MCU raises unprompted —
everything else is commanded by the Pi — because if the Pi itself is down, nothing else can tell
the MCU to alarm.

## Bandwidth

The busiest stream is the 50 Hz sample line: a typical `$D` line (e.g.
`$D,12345,18.2,32.5,410,I*2A\n`) is about 28 bytes, so:

```
50 × 28 bytes  ≈ 1.4 kB/s
```

Adding the 1 Hz status line (~20 B/s) and the 5 Hz heartbeats in both directions (~90 B/s combined)
brings the total to roughly **1.5–1.8 kB/s** — comfortably under the 115200 baud link's raw
capacity of about **11.5 kB/s**, leaving a wide margin for retries, longer detail strings, and
future messages.

## Testing without hardware

Because `protocol.py` has no Qt imports and no dependency on a real serial port, it can be, and is,
fully tested without any hardware:

- `hmi/device/protocol.py` — `checksum`, `encode`/`decode`, and one `encode_*`/parse pair per
  message type.
- `tests/test_protocol.py` — round-trips every message type, and confirms a bad checksum or
  garbage line raises `ProtocolError` instead of being silently accepted.
- `hmi/device/serial_device.py` — the Pi-side driver is tested against a **fake serial port**
  (`tests/test_serial_device.py`), so the polling, heartbeat and link-timeout logic are verified
  without a real MCU. It has not yet been run against real firmware.
