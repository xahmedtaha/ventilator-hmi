# 06 — Raspberry Pi Setup

> **This document is written from documentation, not from a Pi in front of us.** The demo itself
> has been developed and tested on a Windows laptop; every step below should be **verified on the
> actual Raspberry Pi** before a live demo, and adjusted if something on your specific Pi/OS image
> works differently. Where a step depends on the exact Raspberry Pi OS version, that is called out.

## 1. Flash Raspberry Pi OS

Use **Raspberry Pi Imager** on your laptop to flash a microSD card with **Raspberry Pi OS (64-bit,
with desktop)**, for the Pi 4 Model B (4 GB).

Before writing, open the imager's settings (the gear icon) and enable:
- **SSH** (so you can reach the Pi over the network without a keyboard/monitor attached to it)
- **Wi-Fi** (SSID and password for your network)

This lets the Pi be set up "headless" — you never need to plug a keyboard/mouse/monitor into it
directly.

## 2. Copy the project onto the Pi

Either:

```bash
git clone <repository-url> ~/ventilator-hmi
```

or copy the folder over by USB drive / `scp` if the Pi has no direct internet/git access.

## 3. Install Qt and the Python libraries

Try the normal pip route first:

```bash
cd ~/ventilator-hmi
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

PySide6 wheels are large and are not always available for the Pi's architecture/Python version.
**If `pip install` fails on PySide6**, fall back to the system packages instead:

```bash
sudo apt update
sudo apt install python3-pyqt5 python3-pyqtgraph python3-numpy python3-serial
```

and run the app with the **system** `python3` (not the virtual environment) — `hmi/qt.py` imports
Qt through `pyqtgraph.Qt`, which works with PyQt5 just as well as PySide6, so nothing in the app
needs to change.

```bash
python3 main.py
```

## 4. Enable VNC

Current Raspberry Pi OS uses **Wayland** with **wayvnc** as its VNC server (older Raspberry Pi OS
releases used X11 with RealVNC Server instead — if your image is older, the same menu applies, but
double-check which server is actually running).

```bash
sudo raspi-config
```

Go to **Interface Options → VNC → Enable**. Reboot if prompted.

## 5. Set the resolution to 1280×800

The app is designed for a fixed **1280×800** screen (see the design spec, §2). Set this in:

```bash
sudo raspi-config
```

**Display Options** → (resolution setting) — or, from the desktop, the **Screen Configuration**
tool (search for it in the applications menu). If the Pi has **no monitor attached** (fully
headless, driven only through VNC), set a specific headless resolution in the same menu — on
Wayland/wayvnc this is normally exposed under the same Display Options screen; if it is not, check
`wayvnc`'s own configuration file (typically `~/.config/wayvnc/config`) for an `output`/resolution
setting, since headless resolution handling has changed between Raspberry Pi OS releases and should
be confirmed on the actual image you are using.

## 6. Connect from the tablet

On the Samsung tablet, install a VNC viewer app (e.g. **RealVNC Viewer**, available on the Play
Store). Connect to the Pi's IP address (find it with `hostname -I` on the Pi, or check your
router's device list). In the viewer's connection settings, choose **"scale to fit"** so the
1280×800 screen fills the tablet regardless of the tablet's own resolution.

Remember: **VNC carries no audio.** This is exactly why the alarm buzzer is designed to live on
the MCU rather than the Pi — see [docs/02-alarms.md](02-alarms.md).

## 7. Sound (for the demo buzzer)

Plug a small speaker into the Pi's 3.5 mm audio jack. Test it plays before relying on it:

```bash
aplay /usr/share/sounds/alsa/Front_Center.wav
```

If nothing plays, check `raspi-config` → **System Options → Audio** to make sure the 3.5 mm jack
(rather than HDMI) is selected as the output.

(In this software demo phase the buzzer plays on the Pi's own speaker via `aplay`, imitating what
would really be a buzzer on the MCU — see [docs/04-simulator.md](04-simulator.md).)

## 8. Start the HMI

```bash
python3 main.py --fullscreen
```

## 9. Auto-start on boot

Create `~/.config/autostart/ventilator-hmi.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Ventilator HMI
Exec=/home/<user>/ventilator-hmi/.venv/bin/python /home/<user>/ventilator-hmi/main.py --fullscreen
X-GNOME-Autostart-enabled=true
```

Replace `<user>` with your actual username, and adjust the `Exec` path if you installed the
libraries system-wide with `apt` instead of the `.venv` (in that case use `/usr/bin/python3`
instead of `.venv/bin/python`). The HMI will then start automatically the next time the desktop
session starts.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Black screen in the VNC viewer | VNC is enabled but the desktop session has not started, or wayvnc is not actually running — check `sudo systemctl status wayvnc` (or the equivalent RealVNC service on older images) and that you are connecting to the right IP |
| Wrong resolution / window does not fill the screen | The Pi's set resolution is not 1280×800 — recheck Display Options / Screen Configuration (step 5); also confirm the VNC viewer's "scale to fit" is on |
| No sound from the buzzer | 3.5 mm jack not selected as audio output (check `raspi-config` → System Options → Audio), speaker not plugged in fully, or `aplay` reports "no soundcards found" — re-run the `aplay` test in step 7 on its own before blaming the app |
| `ModuleNotFoundError: No module named 'PySide6'` | The pip install of PySide6 failed silently or was skipped — use the `python3-pyqt5` system-package fallback in step 3, and make sure you are running with the matching Python (system `python3`, not a half-set-up `.venv`) |
