#!/bin/bash

# Use Zenity to pick a file
FILE=$(zenity --file-selection --title="Select an Image File")

# Check if a file was selected
if [ -n "$FILE" ]; then
    # Run matugen with the selected file
    matugen image "$FILE"
else
    echo "No file selected."
fi