#!/usr/bin/env python3
"""Send a key directly to projectM's X11 window."""

from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import time

keys = [value.encode("ascii") for value in (sys.argv[1:] or ["n"])]
window_text = subprocess.check_output(["xprop", "-root", "_NET_ACTIVE_WINDOW"], text=True)
match = re.search(r"0x[0-9a-fA-F]+", window_text)
if not match:
    raise SystemExit("no active X11 window")
window = int(match.group(0), 16)
window_class = subprocess.check_output(["xprop", "-id", hex(window), "WM_CLASS"], text=True)
if "projectM-pulseaudio" not in window_class:
    raise SystemExit("active X11 window is not projectM")

x11 = ctypes.CDLL("libX11.so.6")
xtst = ctypes.CDLL("libXtst.so.6")
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
x11.XStringToKeysym.restype = ctypes.c_ulong
x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XKeysymToKeycode.restype = ctypes.c_uint
x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
x11.XSetInputFocus.restype = ctypes.c_int
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XFlush.restype = ctypes.c_int
x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
x11.XCloseDisplay.restype = ctypes.c_int
xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
xtst.XTestFakeKeyEvent.restype = ctypes.c_int

display = x11.XOpenDisplay(None)
if not display:
    raise SystemExit("cannot open X display")
x11.XSetInputFocus(display, window, 2, 0)
for key in keys:
    keysym = x11.XStringToKeysym(key)
    keycode = x11.XKeysymToKeycode(display, keysym)
    if not keycode:
        raise SystemExit("key has no X keycode")
    xtst.XTestFakeKeyEvent(display, keycode, 1, 0)
    xtst.XTestFakeKeyEvent(display, keycode, 0, 0)
    x11.XFlush(display)
    time.sleep(0.12)
x11.XCloseDisplay(display)
