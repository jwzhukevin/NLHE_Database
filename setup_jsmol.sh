#!/bin/bash

# Create necessary directories
mkdir -p app/static/jsmol/j2s
mkdir -p app/static/structures

# Download JSmol
unzip Jmol-14.29.4-binary.zip

# Copy JSmol files
cp jmol-14.29.4/jsmol/* app/static/jsmol/
cp -r jmol-14.29.4/jsmol/j2s/* app/static/jsmol/j2s/

# Clean up
rm -rf jmol-14.29.4
rm Jmol-14.29.4-binary.zip

# Set permissions
chmod -R 755 app/static/jsmol
chmod -R 755 app/static/structures

echo "JSmol setup completed!"