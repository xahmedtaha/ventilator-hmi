# 07 — Demo Guide

A timed script for presenting the demo, about **10 minutes**. Times are approximate — pause
wherever the examiners have questions.

---

## 1. Patient screen (~1.5 min)

Start on the Patient screen (`python main.py`).

- Change the **height** (− / + buttons) and point out that the **IBW** (Ideal Body Weight) and the
  suggested tidal volume range update live.
- Explain: *"We set the tidal volume from IBW, not the patient's actual weight, because an
  overweight patient's lungs are not bigger — ventilating by actual weight over-inflates them.
  This is called lung-protective ventilation: 6 to 8 mL per kg of IBW, and we default to 7."*
- Show the formula text under the IBW number (ARDSNet for adults, Traub & Kichen for pediatric).
- Toggle Category to **Pediatric** and back, to show the ranges and formula change.

## 2. Pre-use check (~2.5 min)

Tap **Next →**.

- Tap **Run all**. Walk through the four tests as they run: system self-test, leak test (accept
  the "block the Y-piece" prompt), compliance & resistance, then calibration + the alarm test —
  point out the flashing red bar and buzzer, and confirm **"I heard and saw it"**.
- Explain: *"ISO 80601-2-12 requires this check before a patient is connected — it's much better
  to find a leak or a dead buzzer on the bench than on a patient."*
- Open the **Demo Panel** (hold the VENT logo 2 s, or press F12). Set **Force pre-use test
  failure → LEAK**, tap **Retry** on the leak test, and show it fails with a realistic leak value.
  Turn the force-fail back to **None**, tap **Retry** again, and show it passes.
- Tap **Continue →** once all four are green.

## 3. Settings (~2 min)

- Tap the **VT** tile and set it to **700 mL**. Point out the tile now has an **orange border and
  note** — explain this is an *advisory* (lung-protective range 6–8 mL/kg), not an alarm; alarm
  colors (red/yellow/cyan) are reserved so they are never confused with this kind of hint. Set VT
  back to a normal value.
- Tap **RR** and try to set it to **40** with **Ti** still at 1.0 s. Show that **Confirm is
  disabled** with a message explaining the inverse-I:E rule (Ti must be ≤ half the breath cycle).
  Cancel out.
- Switch to the **Alarm limits** tab and show the pre-filled limits (from category + IBW), and that
  each is editable the same way as a setting.

## 4. Start ventilation (~1.5 min)

Tap **Start ventilation**, confirm.

- Point at the three waveforms: *"Pressure ramps up in Volume Control because we're holding flow
  constant and the balloon fills; if we were in Pressure Control instead, you'd see a square
  pressure wave and a flow trace that decays instead."*
- Point at the readouts (PIP, PEEP, Vte, RR, etc.) and their small alarm-limit numbers.
- Optionally tap **Modes** and switch to PC to show the waveform shape change, then switch back.

## 5. Alarms (~2.5 min)

Open the **Demo Panel** again (hold VENT logo 2 s, or F12). Inject faults one at a time, letting
each run long enough to reach its alarm (a few seconds to just over a minute, depending on the
alarm's delay — see [docs/02-alarms.md](02-alarms.md) for the exact delays), and reset between
faults with **Reset all faults**.

| Fault to inject | Alarms you will see | What to say |
|---|---|---|
| **Disconnection** | LOW PRESSURE, LOW VTE, LOW MVE | "The circuit is open to atmosphere — this is our disconnection alarm. It's the single most important alarm on a ventilator: if the patient comes off the circuit, we must know immediately." |
| **Occlusion (expiratory)**, VC mode | HIGH PRESSURE, SUSTAINED PRESSURE, LOW VTE | "Air can't leave, so pressure climbs and stays high — SUSTAINED PRESSURE needs 15 continuous seconds above PEEP+15, so it won't fire on a single stiff breath." |
| **Occlusion (expiratory)**, PC mode | LOW VTE, LOW MVE | "In Pressure Control the machine still holds the set pressure, so instead of a pressure alarm you see the delivered volume collapse." |
| **Large leak (50 %)** | LOW VTE, LOW PEEP | "Half the volume never comes back, and the machine can't hold PEEP either — both show up." |
| **Stiff lungs (C ÷ 4)**, VC mode | HIGH PRESSURE | "Same volume, stiffer lungs, so it costs more pressure — that's the V/C term in the lung equation." |
| **Stiff lungs (C ÷ 4)**, PC mode | LOW VTE | "Same pressure, stiffer lungs, so less volume gets in." |
| **Patient effort (fast breathing)** | HIGH RR, HIGH MVE | "The simulated patient is now triggering breaths on their own at 40/min, faster than the set rate — this is what a distressed, spontaneously-breathing patient looks like to the machine." |
| **O2 supply loss** | O2 SUPPLY, then LOW FIO2 | "The MCU reports the O2 supply has failed immediately; FiO2 then drifts toward room air over about 30 seconds before the low-FiO2 alarm fires — that delay avoids a nuisance alarm for a momentary blip." |
| **Battery mode** | ON BATTERY → BATTERY LOW → BATTERY DEPLETED | "Power fails over, battery starts at 25 % here for demo speed, and the alarm escalates as it drains — only the single most severe one is ever shown at once." |
| **MCU link loss** | MCU COMMUNICATION LOST, then APNEA | "The simulated MCU stops talking entirely — the Pi can still show an alarm, but notice we get silence, not sound, because the buzzer lives on the MCU, not the Pi. APNEA follows because no more breaths arrive either." |

Then demonstrate the two operator alarm actions with any alarm still active:
- **Audio Pause** (🔕, top bar): *"Silences the buzzer for up to 120 seconds — the ISO maximum —
  but the visual banner keeps flashing, and a brand-new alarm condition cancels the pause
  immediately, so a real new problem can never be silenced by accident."*
- **Alarm Reset** (↺, top bar): fix or reset the fault first, then tap Reset, and show a
  high-priority alarm move from "resolved" to gone. *"Reset only clears alarms whose condition has
  already ended — it can never make an ongoing problem disappear."*

## 6. Standby (~30 s)

Tap **Standby**, confirm. *"This stops ventilation and returns to Settings — physiological alarms
switch off here, because they wouldn't mean anything with nobody breathing through the circuit."*

---

## Questions examiners may ask

**Q1: Why a separate microcontroller (MCU) instead of doing everything on the Raspberry Pi?**
The Pi runs a general-purpose OS (Linux + Qt + VNC) that is not real-time and not safety-certified.
Sensor reading, valve control and the pressure safety cut-off need to happen on hardware with
deterministic timing and a much simpler, auditable code path — that is what an MCU gives you. The
Pi's job is the human interface; the MCU's job is keeping the patient safe even if the Pi hangs.

**Q2: Why is the buzzer on the MCU, not the Pi?**
Two reasons. First, VNC (how the tablet sees the screen) carries no audio at all, so a Pi-only
buzzer would be inaudible on the tablet anyway. Second, and more importantly: if the Pi freezes or
crashes, the MCU is the only thing left that can still raise an alarm — the design intentionally
does not depend on the Pi being alive to sound a warning.

**Q3: How does latching work, and why only for high-priority alarms?**
A latched (high-priority) alarm keeps being shown, "resolved", after its condition ends, until the
operator explicitly presses Alarm Reset — so a brief but serious event (say, a 20-second
disconnection) cannot silently scroll off screen unnoticed. Medium/low alarms are not latched
because they're judged not serious enough to require that forced acknowledgment; they simply clear
themselves when the condition ends.

**Q4: What is the grace period for?**
For 30 seconds after Start Ventilation, volume/rate/PEEP/FiO2 alarms are muted so the readings can
settle (waveforms take a few breaths to reach steady state). Pressure alarms are *not* muted,
because a disconnection or occlusion in those first 30 seconds is exactly as dangerous as one
later — only the alarms that would otherwise nuisance-trigger during start-up are delayed.

**Q5: How would this actually get certified?**
This software demo follows the *design* requirements of IEC 60601-1-8 and ISO 80601-2-12, but real
certification needs the finished hardware: measured alarm sound levels and flash timing against
the standard's numeric tolerances, a full risk management file (ISO 14971), electrical safety
testing, and independent verification that every documented requirement is actually met in the
built device — none of which a software-only demo can provide.
