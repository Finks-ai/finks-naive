"""
Configuration loader for YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_name: str, config_dir: Path = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_name: Name of config file without extension
        config_dir: Directory containing config files (defaults to project config dir)
        
    Returns:
        Parsed configuration dictionary
    """
    if config_dir is None:
        # Default to project config directory
        config_dir = Path(__file__).parent.parent.parent / "settings"
    
    yaml_path = config_dir / f"{config_name}.yaml"
    
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_config(data: Dict[str, Any], config_name: str, config_dir: Path = None) -> Path:
    """
    Save configuration to YAML file.
    
    Args:
        data: Configuration data to save
        config_name: Name of config file without extension
        config_dir: Directory to save config file (defaults to project config dir)
        
    Returns:
        Path to saved file
    """
    if config_dir is None:
        config_dir = Path(__file__).parent.parent.parent / "settings"
    
    output_path = config_dir / f"{config_name}.yaml"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, 
                 sort_keys=False, allow_unicode=True)
    
    return output_path