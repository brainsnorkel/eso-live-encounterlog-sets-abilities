#!/usr/bin/env python3
"""
Build script for creating standalone installers for Windows and macOS
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return success status"""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
        print(f"Success: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return False

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    print("Installing PyInstaller...")
    return run_command([sys.executable, "-m", "pip", "install", "pyinstaller"])

def create_windows_installer():
    """Create Windows executable using PyInstaller"""
    print("Creating Windows installer...")
    
    # PyInstaller command for Windows
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name=eso-analyzer",
        "--icon=icon.ico",  # We'll need to create this
        "--add-data=setsdb;setsdb",
        "--add-data=example-log;example-log",
        "eso_analyzer.py"
    ]
    
    # Remove icon if it doesn't exist
    if not os.path.exists("icon.ico"):
        cmd.remove("--icon=icon.ico")
    
    return run_command(cmd)

def create_macos_installer():
    """Create macOS executable using PyInstaller"""
    print("Creating macOS installer...")
    
    # PyInstaller command for macOS
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name=eso-analyzer",
        "--add-data=setsdb:setsdb",
        "--add-data=example-log:example-log",
        "eso_analyzer.py"
    ]
    
    return run_command(cmd)

def create_installer_package():
    """Create installer package with dependencies"""
    print("Creating installer package...")
    
    # Create dist directory structure
    dist_dir = Path("dist/installer")
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy executable
    if platform.system() == "Windows":
        exe_name = "eso-analyzer.exe"
        installer_name = "eso-analyzer-windows-installer.exe"
    else:
        exe_name = "eso-analyzer"
        installer_name = "eso-analyzer-macos-installer.dmg"
    
    if os.path.exists(f"dist/{exe_name}"):
        shutil.copy(f"dist/{exe_name}", dist_dir / exe_name)
    
    # Copy additional files
    shutil.copytree("setsdb", dist_dir / "setsdb", dirs_exist_ok=True)
    shutil.copy("README.md", dist_dir / "README.md")
    
    # Create batch/shell script for easy execution
    if platform.system() == "Windows":
        script_content = f"""@echo off
echo ESO Live Encounter Log Sets & Abilities Analyzer
echo.
echo Starting analyzer...
{exe_name} --test-mode
pause
"""
        with open(dist_dir / "run.bat", "w") as f:
            f.write(script_content)
    else:
        script_content = f"""#!/bin/bash
echo "ESO Live Encounter Log Sets & Abilities Analyzer"
echo ""
echo "Starting analyzer..."
./{exe_name} --test-mode
"""
        with open(dist_dir / "run.sh", "w") as f:
            f.write(script_content)
        os.chmod(dist_dir / "run.sh", 0o755)
    
    print(f"Installer package created in: {dist_dir}")
    return True

def main():
    """Main build function"""
    print("ESO Analyzer Installer Builder")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not os.path.exists("eso_analyzer.py"):
        print("Error: eso_analyzer.py not found. Please run this script from the project root.")
        return False
    
    # Install PyInstaller
    if not install_pyinstaller():
        print("Failed to install PyInstaller")
        return False
    
    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # Create installer based on platform
    success = False
    if platform.system() == "Windows":
        success = create_windows_installer()
    elif platform.system() == "Darwin":  # macOS
        success = create_macos_installer()
    else:
        print(f"Unsupported platform: {platform.system()}")
        return False
    
    if not success:
        print("Failed to create executable")
        return False
    
    # Create installer package
    if not create_installer_package():
        print("Failed to create installer package")
        return False
    
    print("\n" + "=" * 40)
    print("Build completed successfully!")
    print("Check the 'dist/installer' directory for the installer package.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
