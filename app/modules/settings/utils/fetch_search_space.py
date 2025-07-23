"""
Fetch possible values for each field from the master_search collection.
This helps understand the search space for fields like company_sector.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from app.core.database import get_db_service
from loguru import logger


def fetch_field_values() -> Dict[str, List[Any]]:
    """Fetch all distinct values for each field in master_search collection."""
    db_service = get_db_service()
    collection = db_service.get_collection("master_search")
    
    # Get a sample document to identify all fields
    sample_doc = collection.find_one()
    if not sample_doc:
        logger.error("No documents found in master_search collection")
        return {}
    
    # Get all field names (excluding _id)
    fields = [field for field in sample_doc.keys() if field != "_id"]
    logger.info(f"Found {len(fields)} fields in master_search collection")
    
    field_values = {}
    
    for field in fields:
        try:
            # Get distinct values for this field
            distinct_values = collection.distinct(field)
            
            # Filter out None/null values
            distinct_values = [v for v in distinct_values if v is not None]
            
            # Sort values for consistency
            if distinct_values and isinstance(distinct_values[0], (str, int, float)):
                distinct_values.sort()
            
            field_values[field] = distinct_values
            
            # Log summary
            if len(distinct_values) <= 20:
                logger.info(f"{field}: {len(distinct_values)} values - {distinct_values}")
            else:
                logger.info(f"{field}: {len(distinct_values)} values - {distinct_values[:5]}... (truncated)")
                
        except Exception as e:
            logger.error(f"Error fetching values for field {field}: {e}")
            field_values[field] = []
    
    return field_values


def analyze_field_types(field_values: Dict[str, List[Any]]) -> Dict[str, Dict]:
    """Analyze field types and characteristics."""
    field_analysis = {}
    
    for field, values in field_values.items():
        analysis = {
            "count": len(values),
            "type": "unknown",
            "sample_values": []
        }
        
        if not values:
            analysis["type"] = "empty"
        elif all(isinstance(v, bool) for v in values):
            analysis["type"] = "boolean"
            analysis["values"] = values
        elif all(isinstance(v, (int, float)) for v in values):
            analysis["type"] = "numeric"
            analysis["min"] = min(values)
            analysis["max"] = max(values)
            analysis["sample_values"] = values[:10]
        elif all(isinstance(v, str) for v in values):
            analysis["type"] = "string"
            if len(values) <= 50:  # Likely categorical
                analysis["subtype"] = "categorical"
                analysis["values"] = values
            else:
                analysis["subtype"] = "text"
                analysis["sample_values"] = values[:10]
        else:
            analysis["type"] = "mixed"
            analysis["sample_values"] = values[:10]
        
        field_analysis[field] = analysis
    
    return field_analysis


def generate_search_space_configs(settings_dir: Path) -> bool:
    """
    Generate search space configuration files from database.
    
    Args:
        settings_dir: Path to settings directory
        
    Returns:
        True if successful, False otherwise
    """
    from datetime import datetime
    
    try:
        logger.info("Fetching search space from master_search collection...")
        
        # Fetch all field values
        field_values = fetch_field_values()
        
        # Analyze field types
        field_analysis = analyze_field_types(field_values)
        
        # Save raw values (for reference)
        raw_output = settings_dir / "search_space_raw.json"
        with open(raw_output, 'w') as f:
            json.dump(field_values, f, indent=2, default=str)
        logger.info(f"Saved raw values to: {raw_output}")
        
        # Save analysis
        analysis_output = settings_dir / "search_space_analysis.yaml"
        with open(analysis_output, 'w') as f:
            # Write timestamp comment
            f.write(f"# Search space field analysis\n")
            f.write(f"# updated_at: {datetime.utcnow().isoformat()}Z\n\n")
            yaml.dump(field_analysis, f, default_flow_style=False, sort_keys=True)
        logger.info(f"Saved analysis to: {analysis_output}")
        
        # Save categorical fields only (useful for field instructions)
        categorical_output = settings_dir / "search_space_categorical.yaml"
        categorical_fields = {}
        
        for field, analysis in field_analysis.items():
            if analysis["type"] == "string" and analysis.get("subtype") == "categorical":
                categorical_fields[field] = {
                    "values": analysis["values"],
                    "count": analysis["count"]
                }
            elif analysis["type"] == "boolean":
                categorical_fields[field] = {
                    "values": analysis["values"],
                    "count": analysis["count"]
                }
        
        with open(categorical_output, 'w') as f:
            # Write timestamp comment
            f.write(f"# Categorical field values for search space\n")
            f.write(f"# updated_at: {datetime.utcnow().isoformat()}Z\n\n")
            yaml.dump(categorical_fields, f, default_flow_style=False, sort_keys=True)
        logger.info(f"Saved categorical fields to: {categorical_output}")
        
        # Print summary
        print("\n" + "="*80)
        print("SEARCH SPACE SUMMARY")
        print("="*80)
        
        print(f"\nTotal fields: {len(field_analysis)}")
        
        # Group by type
        type_counts = defaultdict(int)
        for field, analysis in field_analysis.items():
            type_counts[analysis["type"]] += 1
        
        print("\nField types:")
        for field_type, count in sorted(type_counts.items()):
            print(f"  - {field_type}: {count}")
        
        # Show categorical fields
        print("\nCategorical fields (with value counts):")
        for field, info in sorted(categorical_fields.items()):
            print(f"  - {field}: {info['count']} values")
            if field == "company_sector" or "sector" in field.lower():
                print(f"    Values: {info['values']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error generating search space configs: {e}")
        return False
    finally:
        # Close database connection
        db_service = get_db_service()
        db_service.close()


def main():
    """Main function for command line usage."""
    import sys
    from pathlib import Path
    
    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
    
    # Get settings directory (from command line or default)
    if len(sys.argv) > 1:
        settings_dir = Path(sys.argv[1])
    else:
        # Default to project settings directory
        settings_dir = Path(__file__).parent.parent.parent.parent.parent / "settings"
    
    if not settings_dir.exists():
        print(f"Error: Settings directory not found: {settings_dir}")
        sys.exit(1)
    
    success = generate_search_space_configs(settings_dir)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()