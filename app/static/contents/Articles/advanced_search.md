---
title: "Advanced Search Techniques"
date: "2025-11-15 09:00"
author: "Admin"
summary: "The Materials Database offers powerful search capabilities beyond basic keyword searching. This article explains how to use advanced search features to find exactly what you need."
keywords:
  - Search
  - Boolean
  - Query
  - Filter
---

# Advanced Search Techniques

## Introduction

The Materials Database offers powerful search capabilities beyond basic keyword searching. This article explains how to use advanced search features to find exactly what you need.

## Boolean Operators

Combine search terms using Boolean operators:

- **AND**: Find materials matching all specified criteria
  - Example: `semiconductor AND bandgap>2.0`
- **OR**: Find materials matching any of the specified criteria
  - Example: `metal OR semimetallic`
- **NOT**: Exclude materials matching certain criteria
  - Example: `metal NOT oxidized`

## Property Range Searches

Search for materials with properties in specific ranges:

- Bandgap between 1.0 and 2.0 eV: `bandgap:1.0-2.0`
- Formation energy below -0.5 eV/atom: `formation_energy:<-0.5`
- Work function above 4.5 eV: `workfunction:>4.5`

## Structure-Based Searches

Find materials based on structural characteristics:

- Specific crystal system: `crystal_system:cubic`
- Number of atoms in unit cell: `num_atoms:4-8`
- Contains specific elements: `elements:Si,O`

## Combining Search Methods

For more precise results, combine different search methods:

```
elements:Si,O AND bandgap:>2.0 AND crystal_system:hexagonal
```

This will find hexagonal silicon oxide materials with bandgaps greater than 2.0 eV.

## Saved Searches

Save frequently used searches for quick access:

1. Perform your search
2. Click "Save Search" in the upper right
3. Give your search a descriptive name
4. Access saved searches from your dashboard

## Export Search Results

After finding materials of interest:

1. Select materials from search results
2. Click "Export" button
3. Choose format (CSV, JSON, etc.)
4. Download the data for further analysis

Using these advanced search techniques will help you quickly find relevant materials for your research or applications. 