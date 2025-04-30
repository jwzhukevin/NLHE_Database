# Version 2.0 Release Notes

**Release Date:** June 15, 2023

## Major Features

### New Material Structure Visualization

- Integrated 3D crystal structure viewer with multiple visualization modes
- Added support for polyhedra and bond visualization
- Implemented measurement tools for distances, angles, and planes

### Enhanced Search Capabilities

- Added advanced filtering options for all material properties
- Implemented Boolean search operators (AND, OR, NOT)
- Created saved search functionality with notifications for new matching materials

### User Interface Improvements

- Complete redesign of the material detail pages
- New dashboard with customizable widgets
- Responsive design for mobile and tablet devices

## Minor Improvements

- Increased upload file size limit to 100MB
- Added batch export functionality
- Improved performance for large dataset searches
- Added support for additional file formats (POSCAR, CONTCAR)

## Database Enhancements

- Added 5,000+ new materials to the database
- Updated property calculations for all existing materials
- Enhanced metadata with provenance information
- Added DOIs for each material for citation purposes

## Bug Fixes

- Fixed incorrect band structure rendering for certain material types
- Resolved search indexing issues for complex queries
- Fixed file download errors for large structure files
- Corrected unit conversion in formation energy calculations

## API Changes

- Released v2 of the REST API with expanded endpoints
- Added GraphQL support for complex queries
- Implemented rate limiting and improved authentication
- Added bulk operation endpoints for efficient data access

## Migration Notes

Users upgrading from version 1.x should note:

1. User accounts require password reset due to improved security
2. Custom collections will be automatically migrated
3. API keys from v1 will continue to work but are deprecated
4. Saved searches need to be recreated with the new search syntax

For detailed documentation on new features, please visit the Help section. 