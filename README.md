# Blackdrop

[![Tip with X Money](tip-with-x-money.png)](https://x.com/scottito22)

Blackdrop brings the nostalgia of classic Winamp visualizations to Omarchy as a modern fullscreen listen mode for any display. Its music-reactive motion, true-black silent state, and moving logo are OLED-friendly, so an OLED can stay on while you listen without parking static player chrome on the panel.

![Blackdrop fullscreen visualization](preview.png)

<details>
<summary>More visualization styles</summary>

![Harlequin Vortex](examples/harlequin-vortex.png)

![Solarized Space](examples/solarized-space.png)

</details>

- Click the droplet in the right side of the bar or press **Super+Shift+B**.
- Blackdrop visualizes the PipeWire default sink through projectM on the currently focused display.
- While open it inhibits idle, keeping the display and its audio path alive while preventing the stock screensaver and display-off path from taking over.
- With no sink signal it switches to the official neon-green Omarchy logo drifting on true black.
- While music plays, the visualization is unobstructed most of the time; roughly every four minutes, the neon Omarchy mark flashes for three detected beats. projectM’s M/headphone splash is skipped automatically.
- Twelve curated styles were selected for strong bass/mid/treble-driven equations, then augmented with bass zoom, mid rotation, treble warp, and waveform scaling so the picture visibly dances with the music instead of merely animating autonomously. A chosen preset remains unchanged for the song. **Left/Right** selects the previous/next style, **Up** saves (locks) it, and **Down** unlocks it and enables **Random per song**. Each change shows the preset name and arrow controls for two seconds.
- The pointer is hidden while Blackdrop is open. Press **Escape** or **Super+Shift+B** again to stop; the previous app returns in exactly its prior tiled or fullscreen state.

The overlay follows the focused output and its scale, resolution, and top/bottom/left/right bar placement. Rendering is capped at 60 fps.

## Install

Blackdrop requires Omarchy 4 Quattro plus the repository `projectm` and `projectm-pulseaudio` packages:

```bash
omarchy-pkg-add projectm projectm-pulseaudio
omarchy plugin add https://github.com/jcarcinogen/omarchy-blackdrop.git --enable --yes
~/.config/omarchy/plugins/io.github.jcarcinogen.blackdrop/install-local.py
omarchy-restart-shell
```

The explicit setup step caps projectM at 60 fps, installs the reversible Super+Shift+B binding/window rules, and points projectM at Blackdrop’s curated presets. It never modifies `$OMARCHY_PATH` or replaces the Omarchy screensaver launcher.

## Remove

Run:

```bash
~/.config/omarchy/plugins/io.github.jcarcinogen.blackdrop/uninstall.sh
```

The remover disables the plugin, removes its owned keybinding/window-rule block, restores the prior projectM config, and deletes the plugin tree. It does not touch Omarchy's screensaver launcher and leaves the repository packages installed.
