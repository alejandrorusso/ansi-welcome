#!/bin/bash

# Script to randomly pick and render ANSI art files
# Usage: ./random-ansi.sh

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

# Print the filename (strip leading ./)
echo "=== ${random_file#./} ==="
echo

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
            # Number of comment lines is at byte offset 104 in the SAUCE record
            local num_comments=$(dd if="$file" bs=1 skip=$((size - 128 + 104)) count=1 2>/dev/null | od -An -tu1 | tr -d ' ')
            if [ "$num_comments" -gt 0 ] 2>/dev/null; then
                # COMNT block = 5-byte "COMNT" header + num_comments * 64 bytes
                local comnt_size=$((5 + num_comments * 64))
                local comnt_check=$(dd if="$file" bs=1 skip=$((cut_at - comnt_size)) count=5 2>/dev/null)
                if [ "$comnt_check" = "COMNT" ]; then
                    cut_at=$((cut_at - comnt_size))
                fi
            fi
            # Strip trailing EOF marker (0x1A) if present just before SAUCE/COMNT
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

# Check if file likely needs CP437 conversion (typically .ans files from DOS)
if [[ "$random_file" == *.ans ]]; then
    # Try CP437 conversion first for .ans files
    if strip_sauce "$random_file" | iconv -f cp437 -t utf-8 2>/dev/null; then
        :  # Success, do nothing
    else
        # Fallback to regular cat if conversion fails
        strip_sauce "$random_file"
    fi
else
    # For .ansi and .txt files, use regular cat
    strip_sauce "$random_file"
fi

# Reset terminal attributes, move cursor below all content, and ensure prompt starts on a new line
# \e[0m   - reset all text attributes (colors, bold, etc.)
# \e[999B - move cursor down 999 rows (stops at bottom of content)
# \e[999D - move cursor to leftmost column
printf '\e[0m\e[999B\e[999D\n'