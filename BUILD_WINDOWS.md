# Building the Windows App and Installer

## Prerequisites

1. **Windows 10/11** with **Python 3.9+** (3.11 recommended)
2. **Inno Setup 6** for the installer (`winget install JRSoftware.InnoSetup`); GitHub's `windows-latest` runners have `iscc` preinstalled
3. Dependencies:
   ```cmd
   pip install -r requirements.txt
   pip install -r requirements-build.txt
   ```

## Build steps

1. **Generate gear set data** (required whenever `data/gear_sets/LibSets_SetData.xlsm` changes):
   ```cmd
   python scripts/generate_gear_data.py
   ```

2. **Create the icon** (writes `icon.ico` at the repo root):
   ```cmd
   python scripts/create_icon.py
   ```

3. **Run the tests**:
   ```cmd
   python -m pytest tests/ -q
   ```

4. **Build the GUI executable** (onedir, windowed — output in `dist\esolog-gui\`):
   ```cmd
   python -m PyInstaller esolog-tail.spec --noconfirm
   ```
   Sanity check: `dist\esolog-gui\esolog-gui.exe` should open the main window.

5. **Compile the installer** (output `dist\esolog-tail-windows-setup-<version>.exe`):
   ```cmd
   iscc /DAppVersion=0.3.0 installer\esolog-gui.iss
   ```
   The installer is per-user (no admin), registers in Apps & Features, and upgrades in place thanks to a stable `AppId`. Uninstalling leaves the user's config and archived logs untouched.

6. **Portable zip** (optional):
   ```cmd
   powershell Compress-Archive -Path dist\esolog-gui\* -DestinationPath dist\esolog-tail-windows-portable-0.3.0.zip
   ```

## CI

`.github/workflows/build-installers.yml` runs all of the above on `windows-latest` for pull requests, manual dispatch, and `v*` tags; tagged builds attach the installer and portable zip to the GitHub release. There is no code signing — SmartScreen shows "unknown publisher" (documented in the README).

## Versioning

The single source of truth is `src/version.py`. CI reads it for artifact names and passes it to Inno via `/DAppVersion`.
