#!/usr/bin/env python3
"""
Process VIC CSV file to generate field_instructions.json from filters.csv.
"""

import csv
import yaml
import re
from pathlib import Path


def clean_db_field(field_str):
    """Extract the field name from db_table column, removing Notion links."""
    # Remove Notion URL in parentheses
    field_clean = re.sub(r'\s*\(https://[^)]+\)', '', field_str)
    return field_clean.strip()


def format_instructions(fe_label, instructions):
    """Format the instructions with field label and description."""
    # Combine label and instructions
    return f"{fe_label}\n{instructions}"


def process_csv(csv_path):
    """Process CSV file and generate field instructions."""
    field_instructions = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Extract field name (removing Notion link)
            db_field = clean_db_field(row['db_table'])
            
            # Skip empty or invalid entries
            if not db_field or db_field == 'n/a':
                continue
                
            # Extract FE Label and Instructions
            fe_label = row['FE Label']
            instructions = row['Instructions For LLM']
            
            # Format the complete instruction
            if fe_label and instructions:
                field_instructions[db_field] = format_instructions(fe_label, instructions)
    
    return field_instructions


def main():
    """Main function to generate field_instructions.json from VIC CSV."""
    # Path to CSV file in config directory
    csv_path = Path(__file__).parent.parent / "config" / "filters.csv"
    
    # Output path
    output_path = Path(__file__).parent.parent / "config" / "field_instructions.yaml"
    
    print(f"Processing CSV file: {csv_path}")
    
    # Process CSV
    field_instructions = process_csv(csv_path)
    
    print(f"Extracted {len(field_instructions)} field instructions")
    
    # Write to YAML with proper formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml_lines = [
            "# Natural language interpretation instructions for each field",
            "# Generated from VIC CSV file",
            ""
        ]
        
        for field, instruction in field_instructions.items():
            yaml_lines.append(f"{field}: |")
            for line in instruction.strip().split('\n'):
                yaml_lines.append(f"  {line}")
            yaml_lines.append("")
        
        f.write('\n'.join(yaml_lines))
    
    print(f"Generated: {output_path}")
    
    # Show sample entries
    print("\nSample entries:")
    for i, (field, instruction) in enumerate(field_instructions.items()):
        if i >= 3:
            break
        print(f"\n{field}:")
        print(f"  {instruction[:100]}...")


if __name__ == "__main__":
    main()
