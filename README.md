# MotionPaper

MotionPaper is a Tkinter GUI for applying wallpapers from Steam Wallpaper Engine through `linux-wallpaperengine`.

Note that this was developed with the [`caelestia`](https://github.com/caelestia-dots/shell) rice in mind. Hyprpaper support is extremely experimental and not tested, therefore pull requests for Hyprpaper support (as well as other wallpaper backends) are welcome.

## Install (pipx)

`pipx` is the recommended Linux install path:

1. Install `pipx` (once):

```bash
# Debian/Ubuntu
sudo apt install pipx
pipx ensurepath
```

2. Install MotionPaper from GitHub:

```bash
pipx install "git+https://github.com/kaemori/motionpaper.git"
```

3. Install desktop entries:

```bash
motionpaper-install
```

4. Launch:

```bash
motionpaper
```

## Install (curl bootstrap)

For a one-command install flow, use the bootstrap installer script:

```bash
curl -fsSL https://raw.githubusercontent.com/kaemori/motionpaper/main/install.sh | bash
```

You can also run it with an explicit repository URL:

```bash
curl -fsSL https://raw.githubusercontent.com/kaemori/motionpaper/main/install.sh | bash -s -- "git+https://github.com/kaemori/motionpaper.git"
```

## Commands

- `motionpaper`: launch the GUI
- `motionpaper-daemon`: launch the daemon only
- `motionpaper-install`: install desktop entries under `~/.local/share/applications`

## Local Development

If you are developing from source, you can still run the compatibility scripts:

```bash
./launch.sh
./daemon.sh
./install_to_desktop.sh
```

The launcher scripts prefer `./.venv/bin/python3` when present and fall back to `python3` from your `PATH`.

## Project Layout

```
motionpaper/
├── motionpaper/                  # Python package (shared app logic)
│   ├── config_store.py           # Config and themes loading/saving
│   ├── constants.py              # Paths, version, and app constants
│   ├── daemon_control.py         # GUI-facing daemon start/stop helpers
│   ├── daemon_runtime.py         # Daemon implementation
│   ├── gui_helpers.py            # Shared UI utility functions
│   ├── installer.py              # pipx-friendly desktop entry installer
│   ├── romanization.py           # JP/CN/KR title romanization
│   ├── wallpaper_library.py      # Workshop wallpaper metadata loader
│   └── resources/
│       ├── icon.png              # Packaged icon used by motionpaper-install
│       └── themes.json           # Packaged themes used at runtime
├── gui.py                        # GUI entrypoint module
├── main.py                       # Daemon entrypoint module
├── pyproject.toml                # Packaging metadata and entry points
├── install.sh                    # Curl/bootstrap installer
├── scripts/
│   ├── launch_gui.sh
│   ├── launch_daemon.sh
│   └── install_desktop_entries.sh
├── desktop/
│   ├── motionpaper.desktop
│   └── motionpaper-daemon.desktop
├── assets/
│   └── icon.png
├── config/
│   └── themes.json
├── launch.sh                     # Compatibility wrapper -> scripts/launch_gui.sh
├── daemon.sh                     # Compatibility wrapper -> scripts/launch_daemon.sh
└── install_to_desktop.sh         # Compatibility wrapper -> scripts/install_desktop_entries.sh
```

## Notes

- Config is stored at `~/.config/motionpaper/config.json`.
- The daemon PID file is stored at `/tmp/motionpaper-daemon.pid`.
- Wallpaper discovery uses Steam workshop path `~/.local/share/Steam/steamapps/workshop/content/431960`.
