#!/usr/bin/env python3
"""
Pre-build script to extract gear set data from LibSets_SetData.xlsm
and generate an efficient Python module with optimized data structures.

This eliminates the need to parse Excel files at runtime and reduces
installer size by removing the XLSM dependency.
"""

import pandas as pd
import os
from pathlib import Path
from typing import Dict, List, Set

def extract_gear_data():
    """Extract gear set data from the XLSM file."""
    current_dir = Path(__file__).parent
    excel_file_path = current_dir / "setsdb" / "LibSets_SetData.xlsm"
    
    if not excel_file_path.exists():
        print(f"Warning: Excel file not found: {excel_file_path}")
        return None
    
    try:
        # Read the Excel file
        excel_file = pd.ExcelFile(excel_file_path)
        df = pd.read_excel(excel_file, sheet_name='Sets data', header=1)
        
        print(f"Extracted {len(df)} gear sets from {excel_file_path}")
        
        # Extract the data we need
        gear_data = {
            'set_id_to_name': {},
            'set_name_to_id': {},
            'set_info': {},
            'known_item_mappings': {},
            'known_ability_mappings': {}
        }
        
        # Process each row
        for _, row in df.iterrows():
            set_id = row.get('ESO ingame setId')
            set_name_en = row.get('Name EN')
            set_type = row.get('Set Type', '')
            comment = row.get('Comment', '')
            
            if pd.notna(set_id) and pd.notna(set_name_en):
                set_id_str = str(int(set_id))
                set_name = str(set_name_en).strip().strip('"').replace("\\'", "'")
                
                # Build mappings
                gear_data['set_id_to_name'][set_id_str] = set_name
                gear_data['set_name_to_id'][set_name] = set_id_str
                
                # Store set info
                gear_data['set_info'][set_name] = {
                    'set_id': set_id_str,
                    'set_type': str(set_type) if pd.notna(set_type) else '',
                    'comment': str(comment) if pd.notna(comment) else '',
                    'items': [],
                    'abilities': []
                }
        
        # Add known item and ability mappings (from the current fallback data)
        gear_data['known_item_mappings'] = {
            '154691': "Bahsei's Mania",
        }
        
        gear_data['known_ability_mappings'] = {
            '154691': "Bahsei's Mania",
            '66899': "Spell Power Cure", 
            '107202': "Arms of Relequen",
            '107203': "Arms of Relequen",
            '133378': "Mother Ciannait",
            '84731': "Witchmother's Potent Brew",
        }
        
        return gear_data
        
    except Exception as e:
        print(f"Error extracting gear data: {e}")
        return None

def generate_python_module(gear_data: Dict) -> str:
    """Generate Python module code with the extracted data."""
    
    code = '''"""
Auto-generated gear set data module.
Generated from LibSets_SetData.xlsm - DO NOT EDIT MANUALLY.

This module contains optimized data structures for fast gear set lookups
without requiring Excel file parsing at runtime.
"""

from typing import Dict, List, Optional, Set

# Set ID to Set Name mapping
SET_ID_TO_NAME: Dict[str, str] = {
'''
    
    # Add set ID to name mappings
    for set_id, set_name in sorted(gear_data['set_id_to_name'].items()):
        code += f'    "{set_id}": "{set_name}",\n'
    
    code += '''}

# Set Name to Set ID mapping
SET_NAME_TO_ID: Dict[str, str] = {
'''
    
    # Add set name to ID mappings
    for set_name, set_id in sorted(gear_data['set_name_to_id'].items()):
        code += f'    "{set_name}": "{set_id}",\n'
    
    code += '''}

# Detailed set information
SET_INFO: Dict[str, Dict] = {
'''
    
    # Add set info
    for set_name, info in sorted(gear_data['set_info'].items()):
        code += f'    "{set_name}": {{\n'
        code += f'        "set_id": "{info["set_id"]}",\n'
        code += f'        "set_type": "{info["set_type"]}",\n'
        code += f'        "comment": "{info["comment"]}",\n'
        code += f'        "items": [],\n'
        code += f'        "abilities": []\n'
        code += f'    }},\n'
    
    code += '''}

# Known item ID to set name mappings
KNOWN_ITEM_MAPPINGS: Dict[str, str] = {
'''
    
    # Add known item mappings
    for item_id, set_name in sorted(gear_data['known_item_mappings'].items()):
        code += f'    "{item_id}": "{set_name}",\n'
    
    code += '''}

# Known ability ID to set name mappings
KNOWN_ABILITY_MAPPINGS: Dict[str, str] = {
'''
    
    # Add known ability mappings
    for ability_id, set_name in sorted(gear_data['known_ability_mappings'].items()):
        code += f'    "{ability_id}": "{set_name}",\n'
    
    code += '''}

def get_set_name_by_id(set_id: str) -> Optional[str]:
    """Get set name by set ID."""
    return SET_ID_TO_NAME.get(set_id)

def get_set_id_by_name(set_name: str) -> Optional[str]:
    """Get set ID by set name."""
    return SET_NAME_TO_ID.get(set_name)

def get_set_info(set_name: str) -> Optional[Dict]:
    """Get detailed set information by set name."""
    return SET_INFO.get(set_name)

def get_set_name_by_item_id(item_id: str) -> Optional[str]:
    """Get set name by item ID."""
    return KNOWN_ITEM_MAPPINGS.get(item_id)

def get_set_name_by_ability_id(ability_id: str) -> Optional[str]:
    """Get set name by ability ID."""
    return KNOWN_ABILITY_MAPPINGS.get(ability_id)

# Statistics
TOTAL_SETS = len(SET_ID_TO_NAME)
TOTAL_KNOWN_ITEMS = len(KNOWN_ITEM_MAPPINGS)
TOTAL_KNOWN_ABILITIES = len(KNOWN_ABILITY_MAPPINGS)

def get_stats() -> Dict[str, int]:
    """Get database statistics."""
    return {
        'total_sets': TOTAL_SETS,
        'total_known_items': TOTAL_KNOWN_ITEMS,
        'total_known_abilities': TOTAL_KNOWN_ABILITIES
    }
'''
    
    return code

def main():
    """Main function to generate the gear data module."""
    print("Generating gear set data module...")
    
    # Extract data from XLSM
    gear_data = extract_gear_data()
    if not gear_data:
        print("Failed to extract gear data")
        return 1
    
    # Generate Python module
    python_code = generate_python_module(gear_data)
    
    # Write to file
    output_file = Path(__file__).parent / "gear_set_data.py"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(python_code)
    
    print(f"Generated {output_file}")
    print(f"Statistics:")
    print(f"  - Total sets: {len(gear_data['set_id_to_name'])}")
    print(f"  - Known items: {len(gear_data['known_item_mappings'])}")
    print(f"  - Known abilities: {len(gear_data['known_ability_mappings'])}")
    
    return 0

if __name__ == "__main__":
    exit(main())
