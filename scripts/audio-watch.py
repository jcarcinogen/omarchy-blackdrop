#!/usr/bin/env python3
"""Emit default-sink monitor signal state for Blackdrop.

Also keeps projectM's own capture stream on that sink's monitor, so the
visualizer follows whatever device is playing instead of a remembered one.
"""

from __future__ import annotations

import array
import json
import math
import os
import selectors
import signal
import subprocess
import sys
import time

RATE = 48_000
CHANNELS = 2
LOUD_RMS = 0.0012
SILENCE_HOLD_SECONDS = 1.25
SINK_RECHECK_SECONDS = 2.0
BEAT_RATIO = 1.28
BEAT_COOLDOWN_SECONDS = 0.28
ENERGY_EMA_ALPHA = 0.08

running = True


def stop(_signum: int, _frame: object) -> None:
    global running
    running = False


def emit(message: str) -> None:
    print(message, flush=True)


def default_monitor(run=subprocess.run) -> str:
    result = run(
        ["pactl", "get-default-sink"],
        check=True,
        capture_output=True,
        text=True,
        timeout=3,
    )
    sink = result.stdout.strip()
    if not sink:
        raise RuntimeError("PulseAudio compatibility server has no default sink")
    return sink + ".monitor"


def pactl_json(run, *args: str):
    result = run(
        ["pactl", "-f", "json", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=3,
    )
    return json.loads(result.stdout or "null")


def source_names(run) -> dict[int, str]:
    """Map source index to source name so a stream's target can be compared."""
    try:
        sources = pactl_json(run, "list", "sources") or []
    except Exception:
        return {}
    names = {}
    for source in sources:
        try:
            names[int(source.get("index"))] = str(source.get("name") or "")
        except (TypeError, ValueError):
            continue
    return names


def captures_to_move(streams, names, monitor: str) -> list[int]:
    """Capture streams owned by projectM that are not listening to `monitor`."""
    moves = []
    for stream in streams or []:
        properties = stream.get("properties") or {}
        identity = "{} {}".format(
            properties.get("application.name", ""),
            properties.get("application.process.binary", ""),
        )
        if "projectm" not in identity.lower():
            continue
        try:
            index = int(stream.get("index"))
        except (TypeError, ValueError):
            continue
        current = names.get(stream.get("source")) or str(properties.get("target.object") or "")
        if current != monitor:
            moves.append(index)
    return moves


def align_capture(monitor: str, run=subprocess.run) -> list[int]:
    """Keep projectM listening to the device that is actually playing.

    PipeWire's stream-restore remembers projectM's last capture target, so it can
    come up on an internal-speaker, headset, or HDMI monitor that stays silent
    while audio plays on another device. projectM then renders its idle logo
    screen instead of a preset, which looks exactly like a broken plugin. Moving
    the stream is the only way to correct that after launch.
    """
    try:
        streams = pactl_json(run, "list", "source-outputs") or []
        names = source_names(run)
    except Exception as exc:
        emit("capture-error:" + str(exc).replace("\n", " ")[:200])
        return []
    moved = []
    for index in captures_to_move(streams, names, monitor):
        try:
            run(
                ["pactl", "move-source-output", str(index), monitor],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception as exc:
            emit("capture-error:" + str(exc).replace("\n", " ")[:200])
            continue
        moved.append(index)
        emit("capture:" + monitor)
    return moved


def start_recorder(monitor: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            "parec",
            "--device=" + monitor,
            "--rate=" + str(RATE),
            "--channels=" + str(CHANNELS),
            "--format=float32le",
            "--raw",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
        start_new_session=True,
    )


def terminate(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def rms_f32(chunk: bytes) -> float:
    usable = len(chunk) - (len(chunk) % 4)
    if usable <= 0:
        return 0.0
    samples = array.array("f")
    samples.frombytes(chunk[:usable])
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def align_once(attempts: int = 12, pause: float = 1.0, run=subprocess.run) -> int:
    """Align once for the launcher: projectM's capture appears after it starts.

    Exit status is advisory; the launcher must never fail because the audio
    server was slow to show the stream.
    """
    for attempt in range(attempts):
        try:
            monitor = default_monitor(run)
        except Exception as exc:
            emit("capture-error:" + str(exc).replace("\n", " ")[:200])
            return 1
        if align_capture(monitor, run=run) or attempt == attempts - 1:
            return 0
        time.sleep(pause)
    return 0


def main() -> int:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    proc: subprocess.Popen[bytes] | None = None
    selector = selectors.DefaultSelector()
    monitor = ""
    active = False
    last_loud = 0.0
    last_beat = 0.0
    energy_ema = 0.0
    next_sink_check = 0.0
    emit("silent")

    try:
        while running:
            now = time.monotonic()
            if proc is None or proc.poll() is not None or now >= next_sink_check:
                try:
                    next_monitor = default_monitor()
                    next_sink_check = now + SINK_RECHECK_SECONDS
                    # projectM listens to its own remembered device; keep it on
                    # the one that is actually playing, on every sink check.
                    align_capture(next_monitor)
                    if proc is None or proc.poll() is not None or next_monitor != monitor:
                        if proc and proc.stdout:
                            try:
                                selector.unregister(proc.stdout)
                            except Exception:
                                pass
                        terminate(proc)
                        monitor = next_monitor
                        emit("sink:" + monitor)
                        proc = start_recorder(monitor)
                        if proc.stdout is None:
                            raise RuntimeError("pw-record stdout unavailable")
                        selector.register(proc.stdout, selectors.EVENT_READ)
                        active = False
                        last_loud = 0.0
                        last_beat = 0.0
                        energy_ema = 0.0
                        emit("silent")
                except Exception as exc:
                    emit("error:" + str(exc).replace("\n", " ")[:200])
                    terminate(proc)
                    proc = None
                    time.sleep(1.0)
                    continue

            events = selector.select(timeout=0.2)
            for key, _mask in events:
                chunk = os.read(key.fileobj.fileno(), 16_384)
                if not chunk:
                    terminate(proc)
                    proc = None
                    break
                level = rms_f32(chunk)
                sample_time = time.monotonic()
                if level >= LOUD_RMS:
                    last_loud = sample_time
                    if not active:
                        active = True
                        emit("active")

                    if energy_ema > 0 and level >= energy_ema * BEAT_RATIO \
                            and sample_time - last_beat >= BEAT_COOLDOWN_SECONDS:
                        last_beat = sample_time
                        emit("beat")

                    if energy_ema <= 0:
                        energy_ema = level
                    else:
                        energy_ema += (level - energy_ema) * ENERGY_EMA_ALPHA
                else:
                    energy_ema *= 0.96

            if active and time.monotonic() - last_loud >= SILENCE_HOLD_SECONDS:
                active = False
                emit("silent")
    finally:
        if proc and proc.stdout:
            try:
                selector.unregister(proc.stdout)
            except Exception:
                pass
        terminate(proc)
        selector.close()

    return 0


if __name__ == "__main__":
    if "--align-once" in sys.argv[1:]:
        raise SystemExit(align_once())
    raise SystemExit(main())
