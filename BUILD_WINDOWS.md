# Building Windows Executable

Since the current build environment is macOS, here are instructions for creating a Windows executable:

## Prerequisites

1. **Windows Machine with Python 3.7+**
2. **Install PyInstaller**:
   ```cmd
   pip install pyinstaller
   ```

## Build Instructions

1. **Clone the repository**:
   ```cmd
   git clone https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities.git
   cd eso-live-encounterlog-sets-abilities
   ```

2. **Install dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```

3. **Generate gear set data** (REQUIRED):
   ```cmd
   python scripts/generate_gear_data.py
   ```
   > **Important**: This step extracts gear set data from `data/gear_sets/LibSets_SetData.xlsm` and generates optimized Python data structures. **You must run this step whenever the LibSets spreadsheet is updated with new gear sets.**

4. **Create Windows executable**:
   ```cmd
   pyinstaller --onefile --name=esolog-tail --add-data="data/example_logs;data/example_logs" --icon=icon.ico src/esolog_tail.py
   ```

5. **Create installer package**:
   ```cmd
   mkdir dist\installer
   copy dist\esolog-tail.exe dist\installer\
   copy README.md dist\installer\
   copy run.bat dist\installer\
   ```

6. **Test the executable**:
   ```cmd
   cd dist\installer
   esolog-tail.exe --help
   ```

## Alternative: Use WSL or Docker

If you don't have access to a Windows machine, you can use:

- **WSL (Windows Subsystem for Linux)** with Wine
- **Docker** with a Windows container
- **GitHub Actions** for automated Windows builds

## Gear Set Data Generation

The application uses optimized gear set data that is pre-generated from the LibSets spreadsheet. This process:

1. **Extracts data** from `data/gear_sets/LibSets_SetData.xlsm`
2. **Generates** `gear_set_data.py` with optimized Python data structures
3. **Eliminates** Excel parsing at runtime for faster startup

### When to Regenerate

**You MUST regenerate the gear data when:**
- New gear sets are added to ESO
- The LibSets spreadsheet is updated
- You want to include the latest gear set information

### Manual Regeneration

```cmd
python generate_gear_data.py
```

This will update `gear_set_data.py` with the latest data from the XLSM file.

## Automated Builds

Consider setting up GitHub Actions for automated cross-platform builds:

```yaml
name: Build Executables
on:
  push:
    tags: ['v*']

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt pyinstaller
      - name: Generate gear set data
        run: python scripts/generate_gear_data.py
      - name: Build executable
        run: pyinstaller --onefile --name=esolog-tail src/esolog_tail.py
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: esolog-tail-windows
          path: dist/esolog-tail.exe
```
