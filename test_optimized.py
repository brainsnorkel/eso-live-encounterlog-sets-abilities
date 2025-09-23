#!/usr/bin/env python3
"""
Test script to compare the original vs optimized gear set database approaches.
"""

import time
from gear_set_database import gear_set_db as original_db
from gear_set_database_optimized import gear_set_db as optimized_db

def benchmark_lookup(func, test_data, iterations=1000):
    """Benchmark a lookup function."""
    start_time = time.time()
    for _ in range(iterations):
        for item in test_data:
            func(item)
    end_time = time.time()
    return end_time - start_time

def main():
    print("=== Gear Set Database Performance Comparison ===\n")
    
    # Test data
    set_ids = ['19', '20', '21', '22', '23']
    ability_ids = ['154691', '66899', '107202']
    
    print("Original Database:")
    print(f"  Stats: {original_db.get_stats() if hasattr(original_db, 'get_stats') else 'N/A'}")
    print(f"  Set lookup (19): {original_db.get_set_name_by_set_id('19')}")
    print(f"  Ability lookup (154691): {original_db.get_set_name_by_ability_id('154691')}")
    
    print("\nOptimized Database:")
    print(f"  Stats: {optimized_db.get_stats()}")
    print(f"  Set lookup (19): {optimized_db.get_set_name_by_set_id('19')}")
    print(f"  Ability lookup (154691): {optimized_db.get_set_name_by_ability_id('154691')}")
    
    # Benchmark set ID lookups
    print(f"\n=== Performance Benchmark ({len(set_ids)} items, 1000 iterations) ===")
    
    try:
        original_time = benchmark_lookup(original_db.get_set_name_by_set_id, set_ids)
        print(f"Original database: {original_time:.4f} seconds")
    except Exception as e:
        print(f"Original database failed: {e}")
        original_time = float('inf')
    
    optimized_time = benchmark_lookup(optimized_db.get_set_name_by_set_id, set_ids)
    print(f"Optimized database: {optimized_time:.4f} seconds")
    
    if original_time != float('inf'):
        speedup = original_time / optimized_time
        print(f"Speedup: {speedup:.2f}x faster")
    
    print(f"\n=== File Size Comparison ===")
    import os
    original_size = os.path.getsize('gear_set_database.py')
    optimized_size = os.path.getsize('gear_set_database_optimized.py')
    data_size = os.path.getsize('gear_set_data.py')
    
    print(f"Original database module: {original_size:,} bytes")
    print(f"Optimized database module: {optimized_size:,} bytes")
    print(f"Generated data module: {data_size:,} bytes")
    print(f"Total optimized: {optimized_size + data_size:,} bytes")
    
    if optimized_size + data_size < original_size:
        reduction = original_size - (optimized_size + data_size)
        print(f"Size reduction: {reduction:,} bytes ({reduction/original_size*100:.1f}%)")

if __name__ == "__main__":
    main()
