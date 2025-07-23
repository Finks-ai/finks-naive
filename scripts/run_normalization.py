#!/usr/bin/env python3
"""
Simple runner script for the collection normalization process.
"""

import asyncio
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from normalize_collections import main

if __name__ == "__main__":
    import sys

    print("Starting collection normalization...")
    print("This will create a master_search collection with all fields normalized by symbol.")

    if "--test" in sys.argv:
        print("\nTEST MODE: Processing only first 1000 symbols")
    else:
        print("\nFULL RUN: Processing entire database (89,409 symbols)")
        print("Use --test flag to run on limited dataset for testing")

    print("=" * 60)

    asyncio.run(main())

    print("=" * 60)
    print("Normalization complete!")
    print("You can now query the master_search collection for all symbol data.")
