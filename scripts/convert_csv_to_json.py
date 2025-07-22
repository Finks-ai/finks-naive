#!/usr/bin/env python3
"""
Convert CSV files to JSON format for field mappings and instructions.
This script reads field_names.csv and instruction_mapping.csv and creates
field_mappings.json and field_instructions.json files.
"""

import csv
import json
import os
from pathlib import Path

def load_field_mappings(csv_path):
    """Load field mappings from CSV file."""
    mappings = {}
    
    with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            field_name = row['field_name'].strip()
            collection = row['collection'].strip()
            
            # Skip empty collections
            if collection:
                mappings[field_name] = collection
    
    return mappings

def load_field_instructions(csv_path):
    """Load field instructions from CSV file."""
    instructions = {}
    
    with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            field_name = row['field_name'].strip()
            instruction = row['instruction'].strip()
            
            # Skip empty instructions
            if instruction:
                instructions[field_name] = instruction
    
    return instructions

def create_field_mappings_json(mappings, output_path):
    """Create field_mappings.json file."""
    
    # Get unique collections for descriptions
    collections = set(mappings.values())
    
    # Create collection descriptions
    collection_descriptions = {}
    for collection in collections:
        if collection == "master_profiles":
            collection_descriptions[collection] = "Core company information and basic metrics"
        elif collection == "master_ttm_key_metrics_ratios":
            collection_descriptions[collection] = "TTM (Trailing Twelve Months) financial ratios and key metrics"
        elif collection == "master_analyst_ratings_consensus":
            collection_descriptions[collection] = "Analyst ratings and consensus data"
        else:
            collection_descriptions[collection] = f"Data collection: {collection}"
    
    output_data = {
        "field_mappings": mappings,
        "collection_descriptions": collection_descriptions
    }
    
    with open(output_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(output_data, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"Created {output_path} with {len(mappings)} field mappings")

def create_field_instructions_json(instructions, output_path):
    """Create field_instructions.json file."""
    
    with open(output_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(instructions, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"Created {output_path} with {len(instructions)} field instructions")

def main():
    """Main conversion function."""
    
    # Get the config directory path
    config_dir = Path(__file__).parent.parent / "config"
    
    # Input CSV files
    field_names_csv = config_dir / "field_names.csv"
    instruction_mapping_csv = config_dir / "instruction_mapping.csv"
    
    # Output JSON files
    field_mappings_json = config_dir / "field_mappings.json"
    field_instructions_json = config_dir / "field_instructions.json"
    
    # Check if input files exist
    if not field_names_csv.exists():
        print(f"Error: {field_names_csv} not found")
        return
    
    if not instruction_mapping_csv.exists():
        print(f"Error: {instruction_mapping_csv} not found")
        return
    
    print("Converting CSV files to JSON format...")
    
    # Load data from CSV files
    field_mappings = load_field_mappings(field_names_csv)
    field_instructions = load_field_instructions(instruction_mapping_csv)
    
    # Create JSON files
    create_field_mappings_json(field_mappings, field_mappings_json)
    create_field_instructions_json(field_instructions, field_instructions_json)
    
    print("Conversion completed successfully!")
    print(f"Field mappings: {len(field_mappings)} fields")
    print(f"Field instructions: {len(field_instructions)} fields")
    
    # Show some statistics
    collections = set(field_mappings.values())
    print(f"Collections found: {len(collections)}")
    for collection in sorted(collections):
        count = sum(1 for v in field_mappings.values() if v == collection)
        print(f"  - {collection}: {count} fields")

if __name__ == "__main__":
    main()