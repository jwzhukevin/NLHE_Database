# How to Upload New Materials

## Prerequisites

Before uploading materials to the database, you will need:

1. A CIF file containing the crystal structure
2. Optional: Band structure data file (DAT format)
3. Optional: Material properties in JSON format
4. Optional: Supercell structure file (DAT format)

## Step-by-Step Guide

### 1. Navigate to the Upload Page

Click on the "Add New Material" button on the dashboard or navigate to the Materials > Add New menu item.

### 2. Fill in the Basic Information

- The material name will be automatically extracted from the CIF file
- Select the appropriate status (Done, Unconverged, or Error)

### 3. Upload Required Files

- Click "Browse" to select your CIF structure file
- If available, upload your band structure file
- Add any additional files (properties JSON, SC structure file)

### 4. Enter Material Properties

Complete as many of the following sections as possible:

- **Energy Properties**: Total energy, formation energy, Fermi level
- **Surface Properties**: Vacuum level, work function, metal type
- **Band Structure**: Band gap, VBM energy, CBM energy
- **Coordinates**: VBM and CBM coordinates
- **Band Indexes**: VBM and CBM indices

### 5. Submit the Material

Click the "Create Material" button at the bottom of the form. The system will:

1. Validate all inputs for correctness
2. Process and organize the uploaded files
3. Create a new entry in the database
4. Generate a unique identifier (IMR-XXXXXXXX)

### 6. Verify the Upload

After submission, you will be redirected to the material detail page where you can:

- Verify all information was correctly uploaded
- View the crystal structure
- Analyze band structure (if provided)
- Edit any incorrect information

## Best Practices

- Use consistent units for all numerical values (eV for energies)
- Format coordinates correctly: ['0.333','0.333','0.000']
- Ensure CIF files are properly formatted and validated
- Provide as much information as possible for better searchability

If you encounter any issues during the upload process, please contact the database administrator for assistance. 