#!/bin/bash

# Script to randomly pick and render ANSI art files
# Usage: ./random-ansi.sh          (pick random file each time)
#        ./random-ansi.sh --cache   (use pre-generated cache of 20 shuffled files)

CACHE_FILE="${HOME}/.ansi-welcome-cache"

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

# Generate a new shuffled cache of 20 files
generate_cache() {
    shopt -s nullglob
    local all=(*.ans *.ansi *.txt)
    shopt -u nullglob

    # Exclude source.md
    local filtered=()
    for f in "${all[@]}"; do
        [[ "$f" != "source.md" ]] && filtered+=("$f")
    done

    if [ ${#filtered[@]} -eq 0 ]; then
        echo "No ANSI files found in the current directory!"
        exit 1
    fi

    # Shuffle and pick up to 20
    printf '%s\n' "${filtered[@]}" | shuf | head -20 > "$CACHE_FILE"
}

if [ "$1" = "--cache" ]; then
    # Cache mode: pop the first file from cache, regenerate when empty
    if [ ! -s "$CACHE_FILE" ]; then
        generate_cache
    fi

    # Pop first line
    random_file=$(head -1 "$CACHE_FILE")
    sed -i '1d' "$CACHE_FILE"
else
    # Original mode: pick a random file each time
    shopt -s nullglob
    files=(*.ans *.ansi *.txt)
    shopt -u nullglob

    for i in "${!files[@]}"; do
        [[ "${files[$i]}" == "source.md" ]] && unset 'files[$i]'
    done
    files=("${files[@]}")

    if [ ${#files[@]} -eq 0 ]; then
        echo "No ANSI files found in the current directory!"
        exit 1
    fi

    random_file=${files[$RANDOM % ${#files[@]}]}
fi

# Verify file exists (it might have been removed since cache was built)
if [ ! -f "$random_file" ]; then
    # Invalidate cache and retry
    rm -f "$CACHE_FILE"
    exec "$0" "$@"
fi

# Light reset: clear attributes, clear screen, move cursor home (avoids full "reset" which
# is slow and can break UTF-8 mode)
printf '\e[0m\e[H\e[2J'

# Print the filename
echo "=== ${random_file} ==="
echo

# Strip sauce once, then convert if needed
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT
strip_sauce "$random_file" > "$tmpfile"

if [[ "$random_file" == *.utf8.ans ]]; then
    : # already good
elif [[ "$random_file" == *.ans ]]; then
    # Convert from CP437 if not already valid UTF-8
    if ! iconv -f utf-8 -t utf-8 < "$tmpfile" >/dev/null 2>&1; then
        iconv -f cp437 -t utf-8 < "$tmpfile" 2>/dev/null > "$tmpfile.conv" && mv "$tmpfile.conv" "$tmpfile" || rm -f "$tmpfile.conv"
    fi
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
