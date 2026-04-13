#!/bin/bash

# Script to review ANSI art files one by one
# Files that don't render properly are moved to a quarantine directory
# Usage: ./review-ansi.sh [directory]

SEARCH_DIR="${1:-.}"
QUARANTINE_DIR="$SEARCH_DIR/quarantine"
mkdir -p "$QUARANTINE_DIR"

# Strip SAUCE record (last 128 bytes if it starts with "SAUCE00") and any COMNT block,
# then also remove the EOF marker (0x1A / SUB) if present.
strip_sauce() {
    local file="$1"
    local size=$(stat -c%s "$file")
    local cut_at=$size

    if [ "$size" -gt 128 ]; then
        local sauce_check=$(tail -c 128 "$file" | head -c 7)
        if [ "$sauce_check" = "SAUCE00" ]; then
            cut_at=$((size - 128))
            local num_comments=$(dd if="$file" bs=1 skip=$((size - 128 + 104)) count=1 2>/dev/null | od -An -tu1 | tr -d ' ')
            if [ "$num_comments" -gt 0 ] 2>/dev/null; then
                local comnt_size=$((5 + num_comments * 64))
                local comnt_check=$(dd if="$file" bs=1 skip=$((cut_at - comnt_size)) count=5 2>/dev/null)
                if [ "$comnt_check" = "COMNT" ]; then
                    cut_at=$((cut_at - comnt_size))
                fi
            fi
            if [ "$cut_at" -gt 0 ]; then
                local last_byte=$(dd if="$file" bs=1 skip=$((cut_at - 1)) count=1 2>/dev/null | od -An -tu1 | tr -d ' ')
                if [ "$last_byte" = "26" ]; then
                    cut_at=$((cut_at - 1))
                fi
            fi
            head -c "$cut_at" "$file"
            return
        fi
    fi
    cat "$file"
}

# Find all ANSI files (null-delimited to handle spaces in filenames)
files=()
while IFS= read -r -d '' f; do
    files+=("$f")
done < <(find "$SEARCH_DIR" -maxdepth 1 -type f \( -name "*.ans" -o -name "*.ansi" -o -name "*.txt" \) -not -name "source.md" -print0 | sort -z)

if [ ${#files[@]} -eq 0 ]; then
    echo "No ANSI files found in $SEARCH_DIR!"
    exit 1
fi

total=${#files[@]}
quarantined=0

for i in "${!files[@]}"; do
    file="${files[$i]}"
    name="$(basename "$file")"
    num=$((i + 1))

    # Full terminal reset: clears screen, resets character sets, scroll regions, attributes
    reset
    echo "=== [$num/$total] $name ==="
    echo

    # Render the file
    if [[ "$file" == *.utf8.ans ]]; then
        # Already UTF-8, no conversion needed
        strip_sauce "$file"
    elif [[ "$file" == *.ans ]]; then
        if strip_sauce "$file" | iconv -f cp437 -t utf-8 2>/dev/null; then
            :
        else
            strip_sauce "$file"
        fi
    else
        strip_sauce "$file"
    fi

    # Reset terminal attributes and ensure prompt starts on a new line
    printf '\e[0m\e[999B\e[999D\n'

    echo ""
    # Flush any leftover escape sequences from stdin before prompting
    read -r -d '' -t 0.1 -n 10000 < /dev/tty 2>/dev/null || true
    echo -n "Does this render properly? (y/n/q) "
    read -r answer </dev/tty

    case "$answer" in
        n|N)
            mv "$file" "$QUARANTINE_DIR/"
            quarantined=$((quarantined + 1))
            echo "Moved $name to quarantine."
            sleep 1
            ;;
        q|Q)
            echo "Quitting. Reviewed $num/$total files, quarantined $quarantined."
            exit 0
            ;;
    esac
done

echo "Done! Reviewed $total files, quarantined $quarantined."
