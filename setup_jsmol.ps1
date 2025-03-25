# Create necessary directories
New-Item -ItemType Directory -Force -Path "app\static\jsmol\j2s"
New-Item -ItemType Directory -Force -Path "app\static\structures"

# Download JSmol
$url = "https://sourceforge.net/projects/jmol/files/Jmol/Version%2014.32/Jmol-14.32.36-binary.zip"
$output = "Jmol-14.32.36-binary.zip"
Invoke-WebRequest -Uri $url -OutFile $output

# Extract the zip file
Expand-Archive -Path $output -DestinationPath "."

# Copy JSmol files
Copy-Item "jmol-14.32.36\jsmol\*" -Destination "app\static\jsmol" -Recurse -Force
Copy-Item "jmol-14.32.36\jsmol\j2s\*" -Destination "app\static\jsmol\j2s" -Recurse -Force

# Clean up
Remove-Item -Recurse -Force "jmol-14.32.36"
Remove-Item -Force $output

Write-Host "JSmol setup completed!"