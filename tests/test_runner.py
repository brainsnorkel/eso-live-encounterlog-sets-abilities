#!/usr/bin/env python3
"""
Comprehensive test runner for ESO Live Encounter Log Sets & Abilities Analyzer.
"""

import unittest
import sys
import os
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def discover_and_run_tests(test_dir="tests", pattern="test_*.py", verbosity=2):
    """Discover and run all tests in the specified directory."""
    
    # Get the absolute path to the test directory
    test_path = Path(__file__).parent / test_dir if test_dir != "tests" else Path(__file__).parent
    
    # Discover tests
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(test_path),
        pattern=pattern,
        top_level_dir=str(Path(__file__).parent.parent)
    )
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity, buffer=True)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_unit_tests(verbosity=2):
    """Run only unit tests."""
    print("Running Unit Tests")
    print("=" * 50)
    return discover_and_run_tests("unit", verbosity=verbosity)


def run_integration_tests(verbosity=2):
    """Run only integration tests."""
    print("Running Integration Tests")
    print("=" * 50)
    return discover_and_run_tests("integration", verbosity=verbosity)


def run_all_tests(verbosity=2):
    """Run all tests."""
    print("Running All Tests")
    print("=" * 50)
    return discover_and_run_tests(".", verbosity=verbosity)


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(description="ESO Analyzer Test Runner")
    parser.add_argument(
        "--unit", "-u", 
        action="store_true", 
        help="Run only unit tests"
    )
    parser.add_argument(
        "--integration", "-i", 
        action="store_true", 
        help="Run only integration tests"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Verbose output"
    )
    parser.add_argument(
        "--quiet", "-q", 
        action="store_true", 
        help="Quiet output"
    )
    
    args = parser.parse_args()
    
    # Determine verbosity level
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
    else:
        verbosity = 1
    
    # Determine which tests to run
    success = True
    
    if args.unit:
        success = run_unit_tests(verbosity)
    elif args.integration:
        success = run_integration_tests(verbosity)
    else:
        # Run all tests
        print("ESO Live Encounter Log Sets & Abilities Analyzer - Test Suite")
        print("=" * 70)
        print()
        
        unit_success = run_unit_tests(verbosity)
        print()
        
        integration_success = run_integration_tests(verbosity)
        print()
        
        success = unit_success and integration_success
        
        # Summary
        print("Test Summary")
        print("=" * 50)
        print(f"Unit Tests: {'PASSED' if unit_success else 'FAILED'}")
        print(f"Integration Tests: {'PASSED' if integration_success else 'FAILED'}")
        print(f"Overall: {'PASSED' if success else 'FAILED'}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
