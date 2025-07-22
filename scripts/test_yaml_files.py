#!/usr/bin/env python3
"""
Test script to verify that the YAML files are properly formatted and compatible
with the normalization script.
"""

import yaml
import os
import sys
from pathlib import Path

def test_field_mappings():
    """Test field_mappings.yaml structure."""
    config_path = Path(__file__).parent.parent / "config" / "field_mappings.yaml"
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check structure
        assert "field_mappings" in config, "Missing 'field_mappings' key"
        assert "collection_descriptions" in config, "Missing 'collection_descriptions' key"
        
        field_mappings = config["field_mappings"]
        assert isinstance(field_mappings, dict), "field_mappings should be a dictionary"
        
        print(f"✓ field_mappings.yaml: {len(field_mappings)} fields loaded")
        
        # Show collections
        collections = set(field_mappings.values())
        print(f"✓ Collections found: {len(collections)}")
        for collection in sorted(collections):
            count = sum(1 for v in field_mappings.values() if v == collection)
            print(f"  - {collection}: {count} fields")
        
        return True
        
    except Exception as e:
        print(f"✗ Error loading field_mappings.yaml: {e}")
        return False

def test_field_instructions():
    """Test field_instructions.yaml structure."""
    config_path = Path(__file__).parent.parent / "config" / "field_instructions.yaml"
    
    try:
        with open(config_path, 'r') as f:
            instructions = yaml.safe_load(f)
        
        assert isinstance(instructions, dict), "field_instructions should be a dictionary"
        
        print(f"✓ field_instructions.yaml: {len(instructions)} instructions loaded")
        
        # Show some examples
        print("✓ Sample instructions:")
        count = 0
        for field, instruction in instructions.items():
            if count < 3:
                print(f"  - {field}: {instruction[:100]}...")
                count += 1
        
        return True
        
    except Exception as e:
        print(f"✗ Error loading field_instructions.yaml: {e}")
        return False

def test_field_categories():
    """Test field_categories.yaml structure."""
    config_path = Path(__file__).parent.parent / "config" / "field_categories.yaml"
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        assert "categories" in config, "Missing 'categories' key"
        assert "field_to_category" in config, "Missing 'field_to_category' key"
        
        categories = config["categories"]
        print(f"✓ field_categories.yaml: {len(categories)} categories loaded")
        
        for cat_name, cat_info in categories.items():
            print(f"  - {cat_name}: {cat_info['type']} ({len(cat_info.get('fields', []))} fields)")
        
        return True
        
    except Exception as e:
        print(f"✗ Error loading field_categories.yaml: {e}")
        return False

def test_unavailable_fields():
    """Test unavailable_fields.yaml structure."""
    config_path = Path(__file__).parent.parent / "config" / "unavailable_fields.yaml"
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        assert "unavailable_fields" in config, "Missing 'unavailable_fields' key"
        assert isinstance(config["unavailable_fields"], list), "unavailable_fields should be a list"
        
        print(f"✓ unavailable_fields.yaml: {len(config['unavailable_fields'])} fields marked as unavailable")
        
        return True
        
    except Exception as e:
        print(f"✗ Error loading unavailable_fields.yaml: {e}")
        return False

def test_compatibility():
    """Test compatibility with normalization script."""
    try:
        # Import the normalization script's function
        sys.path.insert(0, str(Path(__file__).parent))
        from normalize_collections import CollectionNormalizer
        
        # Test that it can load the mappings
        normalizer = CollectionNormalizer()
        mappings = normalizer.get_field_to_collection_mapping()
        
        assert isinstance(mappings, dict), "Should return a dictionary"
        assert len(mappings) > 0, "Should have field mappings"
        
        print(f"✓ Normalization script compatibility: {len(mappings)} mappings loaded")
        
        return True
        
    except Exception as e:
        print(f"✗ Compatibility test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing YAML configuration files...")
    print("=" * 50)
    
    success = True
    
    success &= test_field_mappings()
    print()
    
    success &= test_field_instructions()
    print()
    
    success &= test_field_categories()
    print()
    
    success &= test_unavailable_fields()
    print()
    
    success &= test_compatibility()
    print()
    
    if success:
        print("🎉 All tests passed! YAML files are ready for use.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()