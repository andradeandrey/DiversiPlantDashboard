#!/bin/bash

# Script to integrate the recommendation section into index.html

set -e

INDEX_FILE="../query-explorer/static/index.html"
REC_SECTION="../query-explorer/static/recommendation-section.html"
BACKUP_FILE="../query-explorer/static/index.html.backup"

echo "================================================================"
echo "Integrating Recommendation UI into index.html"
echo "================================================================"
echo ""

# Check if files exist
if [ ! -f "$INDEX_FILE" ]; then
    echo "Error: index.html not found at $INDEX_FILE"
    exit 1
fi

if [ ! -f "$REC_SECTION" ]; then
    echo "Error: recommendation-section.html not found at $REC_SECTION"
    exit 1
fi

# Check if already integrated
if grep -q "Plant Diversity Recommendation System" "$INDEX_FILE"; then
    echo "⚠️  Recommendation section already exists in index.html"
    echo ""
    read -p "Do you want to re-integrate (will replace existing)? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Create backup
echo "Creating backup: index.html.backup"
cp "$INDEX_FILE" "$BACKUP_FILE"

echo "Finding insertion point..."

# Find line number of the Custom Query section (we'll insert BEFORE it)
INSERTION_LINE=$(grep -n "<!-- Custom Query -->" "$INDEX_FILE" | head -1 | cut -d: -f1)

if [ -z "$INSERTION_LINE" ]; then
    echo "Error: Could not find insertion point (Custom Query section)"
    echo "Please manually integrate the recommendation section."
    exit 1
fi

echo "Found insertion point at line $INSERTION_LINE"
echo ""

# Split the file and insert recommendation section
head -n $(($INSERTION_LINE - 1)) "$INDEX_FILE" > /tmp/index_part1.html
tail -n +$INSERTION_LINE "$INDEX_FILE" > /tmp/index_part2.html

# Combine
cat /tmp/index_part1.html > "$INDEX_FILE"
echo "" >> "$INDEX_FILE"
cat "$REC_SECTION" >> "$INDEX_FILE"
echo "" >> "$INDEX_FILE"
cat /tmp/index_part2.html >> "$INDEX_FILE"

# Cleanup
rm /tmp/index_part1.html /tmp/index_part2.html

echo "================================================================"
echo "✅ Integration complete!"
echo "================================================================"
echo ""
echo "Changes:"
echo "  - Recommendation section added before Custom Query section"
echo "  - Backup saved: $BACKUP_FILE"
echo ""
echo "To test:"
echo "  1. cd query-explorer"
echo "  2. DEV_MODE=true go run ."
echo "  3. Open http://localhost:8080 in browser"
echo "  4. Scroll down to 'Plant Diversity Recommendation' section"
echo ""
echo "To rollback:"
echo "  cp $BACKUP_FILE $INDEX_FILE"
echo ""
