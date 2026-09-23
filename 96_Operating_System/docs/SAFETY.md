# Hardware Safety Notice

BrisartOS boot images are experimental.

A raw boot image is not a normal application file. If written to the wrong device, it may overwrite important data.

Use safe testing practices:

- Test in an emulator first where possible
- Use disposable media for hardware experiments
- Never write raw images to important drives
- Keep backups
- Verify the target device before any write operation

This repository intentionally does not include destructive disk-write commands.
