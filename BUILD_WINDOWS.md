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

3. **Create Windows executable**:
   ```cmd
   pyinstaller --onefile --name=eso-analyzer --add-data="setsdb;setsdb" --add-data="example-log;example-log" --icon=icon.ico eso_analyzer.py
   ```

4. **Create installer package**:
   ```cmd
   mkdir dist\installer
   copy dist\eso-analyzer.exe dist\installer\
   copy README.md dist\installer\
   xcopy setsdb dist\installer\setsdb\ /E /I
   copy run.bat dist\installer\
   ```

5. **Test the executable**:
   ```cmd
   cd dist\installer
   eso-analyzer.exe --help
   ```

## Alternative: Use WSL or Docker

If you don't have access to a Windows machine, you can use:

- **WSL (Windows Subsystem for Linux)** with Wine
- **Docker** with a Windows container
- **GitHub Actions** for automated Windows builds

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
      - name: Build executable
        run: pyinstaller --onefile --name=eso-analyzer eso_analyzer.py
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: eso-analyzer-windows
          path: dist/eso-analyzer.exe
```
