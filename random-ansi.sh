#!/bin/bash

# Script to randomly pick and render ANSI art files
# Usage: ./random-ansi.sh

# Find all ANSI files (ans, ansi, txt extensions)
files=($(find . -maxdepth 1 -type f \( -name "*.ans" -o -name "*.ansi" -o -name "*.txt" \) -not -name "source.md"))

# Check if any files were found
if [ ${#files[@]} -eq 0 ]; then
    echo "No ANSI files found in the current directory!"
    exit 1
fi

# Pick a random file
random_file=${files[$RANDOM % ${#files[@]}]}

# Check if file likely needs CP437 conversion (typically .ans files from DOS)
if [[ "$random_file" == *.ans ]]; then
    # Try CP437 conversion first for .ans files
    if iconv -f cp437 -t utf-8 "$random_file" 2>/dev/null | cat; then
        :  # Success, do nothing
    else
        # Fallback to regular cat if conversion fails
        cat "$random_file"
    fi
else
    # For .ansi and .txt files, use regular cat
    cat "$random_file"
fi