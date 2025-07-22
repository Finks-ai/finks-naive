#!/usr/bin/env python3
"""
Simple runner script for the collection normalization process.
"""

import sys
import os
import asyncio

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from normalize_collections import main

if __name__ == "__main__":
    print("Starting collection normalization...")
    print("This will create a master_search collection with all fields normalized by symbol.")
    print("="*60)
    
    asyncio.run(main())
    
    print("="*60)
    print("Normalization complete!")
    print("You can now query the master_search collection for all symbol data.")