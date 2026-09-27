# Capability: installer-packaging

## ADDED Requirements

### Requirement: Windows installer for the GUI application
The project SHALL produce a wizard-style Windows installer that installs the GUI application per-user (no administrator rights required), creates a Start Menu entry and optional Desktop shortcut, and registers an uninstaller in Windows Apps & Features.

#### Scenario: Fresh install
- **WHEN** a user runs the installer on a machine without the application
- **THEN** the GUI app is installed under the user's local programs directory, shortcuts are created as selected, and the app launches from the Start Menu

#### Scenario: Uninstall
- **WHEN** the user uninstalls via Apps & Features
- **THEN** installed files and shortcuts are removed, while user configuration and archived logs are left in place

### Requirement: In-place upgrade
The installer SHALL use a stable application identity so that installing a newer version over an existing installation upgrades it in place without requiring manual uninstallation.

#### Scenario: Upgrade
- **WHEN** a user with version N installed runs the installer for version N+1
- **THEN** the installation is replaced with N+1, existing shortcuts keep working, and user settings are preserved

### Requirement: CI-built release artifacts
The release workflow SHALL build the GUI installer and a portable zip of the GUI app on the Windows CI runner and attach both to tagged releases. macOS/Linux build jobs SHALL be removed (Windows-only distribution; no code signing).

#### Scenario: Tagged release
- **WHEN** a version tag `v*` is pushed
- **THEN** the release contains `esolog-tail-windows-setup-<version>.exe` and `esolog-tail-windows-portable-<version>.zip`, and no macOS/Linux artifacts are built
