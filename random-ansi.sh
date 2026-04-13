#!/bin/bash

# Script to randomly pick and render ANSI art files
# Usage: ./random-ansi.sh

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
done < <(find . -maxdepth 1 -type f \( -name "*.ans" -o -name "*.ansi" -o -name "*.txt" \) -not -name "source.md" -print0)

# Check if any files were found
if [ ${#files[@]} -eq 0 ]; then
    echo "No ANSI files found in the current directory!"
    exit 1
fi

# Pick a random file
random_file=${files[$RANDOM % ${#files[@]}]}

# Full terminal reset: clears screen, resets character sets, scroll regions, attributes
reset

# Print the filename (strip leading ./)
echo "=== ${random_file#./} ==="
echo

# Render the file into a temp file
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

if [[ "$random_file" == *.utf8.ans ]]; then
    strip_sauce "$random_file" > "$tmpfile"
elif [[ "$random_file" == *.ans ]]; then
    # Check if file is already valid UTF-8 (pre-converted) or raw CP437
    if strip_sauce "$random_file" | iconv -f utf-8 -t utf-8 >/dev/null 2>&1; then
        strip_sauce "$random_file" > "$tmpfile"
    else
        strip_sauce "$random_file" | iconv -f cp437 -t utf-8 > "$tmpfile" 2>/dev/null || strip_sauce "$random_file" > "$tmpfile"
    fi
else
    strip_sauce "$random_file" > "$tmpfile"
fi

# Smooth scroll if content is taller than the terminal, otherwise show instantly
term_rows=$(tput lines)
file_lines=$(wc -l < "$tmpfile")

if [ "$file_lines" -gt "$term_rows" ]; then
    while IFS= read -r line; do
        printf '%s\n' "$line"
        sleep 0.03
    done < "$tmpfile"
else
    cat "$tmpfile"
fi

# Reset terminal attributes and ensure prompt starts on a new line
printf '\e[0m\n'
