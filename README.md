# ANSI Welcome

A curated collection of classic ANSI art for terminal welcome screens and displays.

## Contents

This directory contains various ANSI art files from different eras of computing:

- **Retro Computers**: Apple II, IBM PC, Commodore 64, Sinclair ZX-Spectrum
- **Classic Games**: Mario Bros, Pac-Man, Breakout, Lode Runner  
- **System Screens**: MS-DOS boot, Windows logos, terminal themes
- **Creative Art**: Hot air balloon, cassette tape, Unix theme

## File Types

- `.ans` - Classic DOS ANSI files (use CP437 encoding)
- `.ansi` - Modern ANSI files (UTF-8 compatible) 
- `.txt` - Text-based ANSI art

## Usage

### View Individual Files

For `.ans` files (DOS-era):
```bash
iconv -f cp437 -t utf-8 filename.ans | cat
```

For `.ansi` and `.txt` files:
```bash
cat filename.ansi
```

### Random Display

Use the included script to display a random ANSI art:
```bash
./random-ansi.sh
```

The script automatically detects file types and applies the appropriate rendering method.

## Technical Notes

- All files have been converted to Unix line endings (`\n`)
- Filenames use hyphens instead of spaces for shell compatibility
- CP437 encoding preserved for authentic DOS-era rendering
- Box-drawing characters require proper font support

## Sources

- https://github.com/PhMajerus/ANSI-art
- https://github.com/NNBnh/ansi

## Tips

- Use a terminal with proper CP437/Unicode support
- Consider retro fonts like "Perfect DOS VGA 437" for authenticity  
- Disable line wrapping for proper display
- Some files may require specific terminal dimensions (80x25)
