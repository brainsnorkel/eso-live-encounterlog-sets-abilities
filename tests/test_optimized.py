#!/usr/bin/env python3
"""
Test script to compare the original vs optimized gear set database approaches.
"""

import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import gear_set_database_optimized

# Only test the optimized database since original is removed
optimized_db = gear_set_database_optimized.gear_set_db

def benchmark_lookup(func, test_data, iterations=1000):
    """Benchmark a lookup function."""
    start_time = time.time()
    for _ in range(iterations):
        for item in test_data:
            func(item)
    end_time = time.time()
    return end_time - start_time

def main():
    print("=== Optimized Gear Set Database Test ===\n")

    # Test data
    set_ids = ['19', '20', '21', '22', '23']
    ability_ids = ['154691', '66899', '107202']

    print("Optimized Database:")
    print(f"  Stats: {optimized_db.stats}")
    print(f"  Set lookup (19): {optimized_db.get_set_name_by_set_id('19')}")
    print(f"  Ability lookup (154691): {optimized_db.get_set_name_by_ability_id('154691')}")

    # Benchmark set ID lookups
    print(f"\n=== Performance Benchmark ({len(set_ids)} items, 1000 iterations) ===")

    optimized_time = benchmark_lookup(optimized_db.get_set_name_by_set_id, set_ids)
    print(f"Optimized database: {optimized_time:.4f} seconds")
    
    print(f"\n=== File Size ===")
    import os
    src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
    optimized_size = os.path.getsize(os.path.join(src_dir, 'gear_set_database_optimized.py'))
    data_size = os.path.getsize(os.path.join(src_dir, 'gear_set_data.py'))

    print(f"Optimized database module: {optimized_size:,} bytes")
    print(f"Generated data module: {data_size:,} bytes")
    print(f"Total: {optimized_size + data_size:,} bytes")

if __name__ == "__main__":
    main()
