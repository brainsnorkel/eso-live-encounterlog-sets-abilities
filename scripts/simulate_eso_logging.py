#!/usr/bin/env python3
"""
ESO Log Simulator

Simulates ESO's encounter logging by reading lines from a source log file
and writing them to a destination file at specified intervals.

This tool is useful for testing the tailing behavior of esolog-tail without
needing to play ESO or wait for real combat encounters.

Usage:
    python3 scripts/simulate_eso_logging.py <source_file> <dest_file> <lines_per_interval> <interval_seconds>
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Optional


def simulate_logging(source_file: Path, dest_file: Path, lines_per_interval: int, interval_seconds: float):
    """
    Simulate ESO logging by copying lines from source to destination at intervals.
    
    Args:
        source_file: Path to source encounter log file
        dest_file: Path to destination log file (will be created/overwritten)
        lines_per_interval: Number of lines to write per interval
        interval_seconds: Time between intervals in seconds
    """
    
    if not source_file.exists():
        print(f"Error: Source file {source_file} does not exist")
        return False
    
    print(f"ESO Log Simulator")
    print(f"Source: {source_file}")
    print(f"Destination: {dest_file}")
    print(f"Lines per interval: {lines_per_interval}")
    print(f"Interval: {interval_seconds} seconds")
    print(f"Press Ctrl+C to stop")
    print()
    
    # Read all lines from source file
    print("Reading source file...")
    try:
        with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
    except Exception as e:
        print(f"Error reading source file: {e}")
        return False
    
    total_lines = len(all_lines)
    print(f"Read {total_lines:,} lines from source file")
    
    if total_lines == 0:
        print("Error: Source file is empty")
        return False
    
    # Initialize destination file
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Start with empty destination file
        with open(dest_file, 'w', encoding='utf-8') as f:
            pass
        
        print(f"Created destination file: {dest_file}")
        print()
        
        lines_written = 0
        interval_count = 0
        
        while lines_written < total_lines:
            interval_count += 1
            remaining_lines = total_lines - lines_written
            lines_to_write = min(lines_per_interval, remaining_lines)
            
            # Write lines to destination file (close and reopen between writes)
            for i in range(lines_to_write):
                line_index = lines_written + i
                with open(dest_file, 'a', encoding='utf-8') as f:
                    f.write(all_lines[line_index])
                    f.flush()  # Ensure data is written to disk
            
            lines_written += lines_to_write
            
            # Print progress
            progress = (lines_written / total_lines) * 100
            print(f"Interval {interval_count}: Wrote {lines_to_write} lines "
                  f"(Total: {lines_written:,}/{total_lines:,}, {progress:.1f}%)")
            
            if lines_written >= total_lines:
                print("Finished writing all lines from source file")
                break
            
            # Wait for next interval
            try:
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print(f"\nStopped by user. Wrote {lines_written:,} lines total.")
                break
        
        print(f"Simulation complete. Final destination file: {dest_file}")
        return True
        
    except Exception as e:
        print(f"Error during simulation: {e}")
        return False


def main():
    """Main entry point with argument parsing."""
    
    parser = argparse.ArgumentParser(
        description="Simulate ESO encounter logging by copying lines from source to destination at intervals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Write 100 lines every 2 seconds
  python3 scripts/simulate_eso_logging.py data/example_logs/Encounter.log test_output.log 100 2.0
  
  # Write 50 lines every 0.5 seconds (faster simulation)
  python3 scripts/simulate_eso_logging.py data/example_logs/Encounter.log test_output.log 50 0.5
  
  # Write 1000 lines every 5 seconds (slower simulation)
  python3 scripts/simulate_eso_logging.py data/example_logs/Encounter.log test_output.log 1000 5.0
        """
    )
    
    parser.add_argument('source_file', type=Path,
                       help='Source encounter log file to read from')
    parser.add_argument('dest_file', type=Path,
                       help='Destination log file to write to')
    parser.add_argument('lines_per_interval', type=int,
                       help='Number of lines to write per interval')
    parser.add_argument('interval_seconds', type=float,
                       help='Time between intervals in seconds')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.lines_per_interval <= 0:
        print("Error: lines_per_interval must be positive")
        sys.exit(1)
    
    if args.interval_seconds <= 0:
        print("Error: interval_seconds must be positive")
        sys.exit(1)
    
    # Run simulation
    success = simulate_logging(
        args.source_file,
        args.dest_file,
        args.lines_per_interval,
        args.interval_seconds
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()