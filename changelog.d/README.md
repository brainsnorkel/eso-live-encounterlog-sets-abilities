# Changelog fragments

Each change adds its release notes here as a file of its own, instead of editing `CHANGELOG.md`. The release commit (`python scripts/release.py minor|patch|X.Y.Z`) gathers every fragment under the new version's heading in `CHANGELOG.md` and removes them. Two pull requests never edit the same file this way, so merging one no longer puts the others in conflict (issue #134).

**Name:** `<issue>-<short-slug>.md`, for example `137-armour-label.md`. Within a section, entries come out in file name order, so the issue number keeps them in a stable order. A change without an issue uses a slug alone.

**Content:** the entry as it would read in `CHANGELOG.md`, under one or more of the headings `### Added`, `### Changed`, `### Deprecated`, `### Removed`, `### Fixed` and `### Security`. Write for the people who use the app: what changed for them, with the issue number.

```markdown
### Fixed
- **Four more Class Masteries show beside the class** (#139): Conservation of Energy, Share the Spoils and Nocturnal Inspiration, which the log writes only as the resources they give, and Devout Guardian
```

A fragment with text outside those headings, or with none of them, is refused when the release is cut, and by the unit tests before that.

A pull request that needs no entry (a typo in the guide, a CI change, tests alone) carries the `no-changelog` label instead. The *Changelog* check on every pull request asks for one or the other, and refuses edits to `CHANGELOG.md` and `docs/design.md`, which only the release commit writes.
