---
title: "Data Export Guide"
date: "2025-11-05 09:00"
author: "Admin"
summary: "The Materials Database allows you to export data in several formats, including CSV, JSON, and CIF files for various analysis needs."
keywords:
  - Export
  - CSV
  - JSON
  - API
---

# Data Export Guide

## Export Options

The Materials Database allows you to export data in several formats:

1. **CSV Format**: For spreadsheet applications (Excel, Google Sheets)
2. **JSON Format**: For programmatic access and analysis
3. **CIF Files**: For structure analysis in crystallographic software
4. **Custom Formats**: For specialized simulation packages

## Exporting Individual Materials

### From the Material Detail Page

To export data for a single material:

1. Navigate to the material's detail page
2. Click the "Export" button in the top right corner
3. Select the desired export format
4. Choose which properties to include
5. Click "Download" to save the file

### Export Content Options

You can customize what data to include:

- **Basic Properties**: Name, ID, status
- **Structure Data**: Unit cell, atomic positions
- **Electronic Properties**: Band gap, Fermi level, workfunction
- **Energetics**: Formation energy, total energy
- **Files**: Include associated files (CIF, band data, etc.)

## Batch Exporting Multiple Materials

### From the Search Results

To export data for multiple materials:

1. Perform a search to find materials of interest
2. Select materials using the checkboxes (or "Select All")
3. Click the "Export Selected" button
4. Choose the export format and options
5. Click "Download" to save the file

### From Collections

If you've created material collections:

1. Navigate to the "Collections" page
2. Open the collection containing your materials
3. Click "Export Collection"
4. Select format and options
5. Download the file

## API Access

For programmatic access to the database:

1. Request an API key from your administrator
2. Use HTTP requests to fetch data:
   ```
   GET /api/v1/materials?property=bandgap&value=>2.0
   ```
3. Responses will be in JSON format by default
4. For large datasets, use pagination parameters:
   ```
   GET /api/v1/materials?limit=100&offset=200
   ```

## Best Practices

- **Selective Export**: Only export the properties you need to keep file sizes manageable
- **Batch Processing**: For very large exports, consider using the API with scripts
- **Data Citation**: Remember to cite the database when using exported data in publications
- **Versioning**: Note the database version/date when exporting for reproducibility

For more information on data formats or custom export needs, please contact the database administrator. 