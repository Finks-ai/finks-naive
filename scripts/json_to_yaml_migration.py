#!/usr/bin/env python3
"""
Migrate JSON configuration files to YAML format with enhanced readability.
"""

import json
import yaml
from pathlib import Path
import sys
from typing import Dict, Any, List
import argparse


class YAMLMigrator:
    """Handle JSON to YAML migration with comments and structure improvements."""
    
    def __init__(self, add_comments: bool = True, backup: bool = True):
        self.add_comments = add_comments
        self.backup = backup
        self.config_dir = Path(__file__).parent.parent / "config"
    
    def migrate_field_mappings(self, data: Dict[str, Any]) -> str:
        """Convert field_mappings.json to YAML with comments."""
        lines = [
            "# Field to MongoDB collection mappings",
            "# This file defines which collection contains each field",
            "# Auto-generated from field_mappings.json",
            "",
            "field_mappings:"
        ]
        
        # Group fields by collection for better organization
        by_collection = {}
        for field, collection in data.get("field_mappings", {}).items():
            if collection not in by_collection:
                by_collection[collection] = []
            by_collection[collection].append(field)
        
        # Add field mappings grouped by collection
        for collection, fields in by_collection.items():
            lines.append(f"  # Fields from {collection}")
            for field in sorted(fields):
                lines.append(f"  {field}: {collection}")
            lines.append("")
        
        # Add collection descriptions
        if "collection_descriptions" in data:
            lines.extend([
                "# Collection descriptions for reference",
                "collection_descriptions:"
            ])
            for collection, desc in data["collection_descriptions"].items():
                lines.append(f"  {collection}: |")
                for line in desc.strip().split('\n'):
                    lines.append(f"    {line}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def migrate_field_categories(self, data: Dict[str, Any]) -> str:
        """Convert field_categories.json to YAML with comments."""
        lines = [
            "# Field categorization for agent processing",
            "# Defines selection rules and groupings",
            "",
            "categories:"
        ]
        
        # Add categories with descriptions
        for category, info in data.get("categories", {}).items():
            lines.append(f"  {category}:")
            lines.append(f"    type: {info['type']}  # {'User can select multiple fields' if info['type'] == 'multiselect' else 'User can select only one field'}")
            if info.get("fields"):
                lines.append("    fields:")
                for field in info["fields"]:
                    lines.append(f"      - {field}")
            lines.append("")
        
        # Add field to category mapping
        if "field_to_category" in data:
            lines.extend([
                "# Reverse mapping for quick field lookups",
                "field_to_category:"
            ])
            for field, category in sorted(data["field_to_category"].items()):
                lines.append(f"  {field}: {category}")
        
        return '\n'.join(lines)
    
    def migrate_field_instructions(self, data: Dict[str, Any]) -> str:
        """Convert field_instructions.json to YAML with multiline strings."""
        lines = [
            "# Natural language interpretation instructions for each field",
            "# Used by the instruction processing agent to understand user intent",
            ""
        ]
        
        # Group by category if possible (load categories for context)
        try:
            categories_path = self.config_dir / "field_categories.json"
            with open(categories_path, 'r') as f:
                categories_data = json.load(f)
            field_to_cat = categories_data.get("field_to_category", {})
            
            # Group instructions by category
            by_category = {"Other": {}}
            for field, instruction in data.items():
                category = field_to_cat.get(field, "Other")
                if category not in by_category:
                    by_category[category] = {}
                by_category[category][field] = instruction
            
            # Output by category
            for category in sorted(by_category.keys()):
                if by_category[category]:
                    lines.append(f"# {category} Fields")
                    for field, instruction in sorted(by_category[category].items()):
                        lines.append(f"{field}: |")
                        for line in instruction.strip().split('\n'):
                            lines.append(f"  {line}")
                        lines.append("")
        except:
            # Fallback to simple conversion
            for field, instruction in sorted(data.items()):
                lines.append(f"{field}: |")
                for line in instruction.strip().split('\n'):
                    lines.append(f"  {line}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def migrate_unavailable_fields(self, data: Dict[str, Any]) -> str:
        """Convert unavailable_fields.json to YAML with comments."""
        lines = [
            "# Fields referenced in documentation but not yet available in database",
            "# These require calculation from historical data",
            "",
            "unavailable_fields:"
        ]
        
        # Add fields with inline comments
        fields_comments = {
            "year_over_year_quarterly_revenue_growth": "YoY revenue growth from quarterly data",
            "year_over_year_quarterly_eps_growth": "YoY EPS growth from quarterly data",
            "5year_annual_total_EPS_growth": "5-year compound annual growth rate for EPS",
            "1year_annual_EPS_growth": "1-year EPS growth rate",
            "5year_annual_total_revenue_growth": "5-year compound annual growth rate for revenue",
            "1year_annual_revenue_growth": "1-year revenue growth rate"
        }
        
        for field in data.get("unavailable_fields", []):
            comment = fields_comments.get(field, "")
            if comment:
                lines.append(f"  - {field}  # {comment}")
            else:
                lines.append(f"  - {field}")
        
        # Add implementation notes
        lines.extend([
            "",
            "# Implementation notes",
            "notes:",
            "  data_source: |",
            "    These metrics can be calculated from master_income_statement collection",
            "    which contains historical revenue and EPS data by fiscal period",
            "  ",
            "  calculation_approach: |",
            "    1. Query master_income_statement for historical data points",
            "    2. Calculate year-over-year changes for quarterly data",
            "    3. Calculate CAGR for multi-year periods",
            "    4. Store results in new collection or update existing documents"
        ])
        
        return '\n'.join(lines)
    
    def migrate_file(self, json_filename: str) -> Path:
        """Migrate a single JSON file to YAML."""
        json_path = self.config_dir / json_filename
        yaml_filename = json_filename.replace('.json', '.yaml')
        yaml_path = self.config_dir / yaml_filename
        
        print(f"Migrating {json_filename} -> {yaml_filename}")
        
        # Load JSON data
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Convert based on file type with custom formatting
        if self.add_comments:
            if "field_mappings" in json_filename:
                yaml_content = self.migrate_field_mappings(data)
            elif "field_categories" in json_filename:
                yaml_content = self.migrate_field_categories(data)
            elif "field_instructions" in json_filename:
                yaml_content = self.migrate_field_instructions(data)
            elif "unavailable_fields" in json_filename:
                yaml_content = self.migrate_unavailable_fields(data)
            else:
                # Generic conversion
                yaml_content = yaml.dump(data, default_flow_style=False, 
                                       sort_keys=False, allow_unicode=True)
        else:
            # Simple conversion without comments
            yaml_content = yaml.dump(data, default_flow_style=False, 
                                   sort_keys=False, allow_unicode=True)
        
        # Write YAML file
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        print(f"  ✓ Created {yaml_path}")
        
        # Validate by loading it back
        try:
            with open(yaml_path, 'r') as f:
                yaml.safe_load(f)
            print(f"  ✓ Validated YAML syntax")
        except yaml.YAMLError as e:
            print(f"  ✗ YAML validation failed: {e}")
            return None
        
        return yaml_path
    
    def migrate_all(self) -> List[Path]:
        """Migrate all JSON config files to YAML."""
        json_files = [
            "field_mappings.json",
            "field_categories.json",
            "field_instructions.json",
            "unavailable_fields.json"
        ]
        
        migrated = []
        for json_file in json_files:
            json_path = self.config_dir / json_file
            if json_path.exists():
                yaml_path = self.migrate_file(json_file)
                if yaml_path:
                    migrated.append(yaml_path)
            else:
                print(f"  ⚠ Skipping {json_file} (not found)")
        
        return migrated


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate JSON configs to YAML")
    parser.add_argument("--no-comments", action="store_true", 
                       help="Skip adding comments and formatting")
    parser.add_argument("--file", type=str, 
                       help="Migrate specific file only")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without making changes")
    
    args = parser.parse_args()
    
    migrator = YAMLMigrator(add_comments=not args.no_comments)
    
    print("JSON to YAML Configuration Migration")
    print("=" * 40)
    
    if args.file:
        # Migrate single file
        if args.dry_run:
            print(f"Would migrate: {args.file}")
        else:
            migrator.migrate_file(args.file)
    else:
        # Migrate all files
        if args.dry_run:
            print("Would migrate all configuration files")
        else:
            migrated = migrator.migrate_all()
            print(f"\n✅ Migrated {len(migrated)} files successfully")
            
            if migrated:
                print("\nNext steps:")
                print("1. Test the application with new YAML configs")
                print("2. Update Python code to use config_loader")
                print("3. Run integration tests")
                print("4. Remove JSON files after verification")


if __name__ == "__main__":
    main()