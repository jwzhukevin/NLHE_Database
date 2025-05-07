#!/bin/bash
# Script to create or update admin user

# Set Flask environment
export FLASK_APP=app

# Show debug information
echo "==============================="
echo "Admin User Creation Script"
echo "==============================="
echo "FLASK_APP = $FLASK_APP"
echo "Current directory: $(pwd)"
echo "NOTE: You will be prompted for username, email, and password"
echo "==============================="

# Ensure database is initialized
echo "Ensuring database is initialized..."
flask initdb
if [ $? -ne 0 ]; then
    echo "Error: Failed to initialize database."
    exit 1
fi

# Run email migration if needed
echo "Checking and running email field migration if needed..."
flask migrate-users-email
if [ $? -ne 0 ]; then
    echo "Warning: Email migration may have encountered issues."
    echo "You might need to recreate the database with 'flask initdb --drop' if problems persist."
fi

# Run admin creation command
echo "Creating/updating admin user..."
flask admin

# Check if command was successful
if [ $? -eq 0 ]; then
    echo "==============================="
    echo "Admin account created/updated successfully!"
    echo "==============================="
else
    echo "==============================="
    echo "Error: Failed to create/update admin account."
    echo "==============================="
    exit 1
fi
