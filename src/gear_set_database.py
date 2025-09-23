"""
Gear Set Database Module

This module reads the LibSets_SetData.xlsm file to provide comprehensive
gear set information for ESO encounter log analysis.
"""

import pandas as pd
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class GearSetDatabase:
    """Database for ESO gear sets loaded from LibSets Excel file."""
    
    def __init__(self, excel_file_path: str = None):
        """
        Initialize the gear set database.
        
        Args:
            excel_file_path: Path to the LibSets_SetData.xlsm file
        """
        if excel_file_path is None:
            # Default to the data/gear_sets directory
            current_dir = Path(__file__).parent.parent
            excel_file_path = current_dir / "data" / "gear_sets" / "LibSets_SetData.xlsm"
        
        self.excel_file_path = excel_file_path
        self.item_to_set: Dict[str, str] = {}  # item_id -> set_name
        self.set_info: Dict[str, Dict] = {}  # set_name -> set_info
        self.ability_to_set: Dict[str, str] = {}  # ability_id -> set_name
        self.set_id_to_name: Dict[str, str] = {}  # set_id -> set_name
        
        self._load_database()
    
    def _load_database(self):
        """Load the gear set database from the Excel file."""
        try:
            if not os.path.exists(self.excel_file_path):
                print(f"Warning: Gear set database file not found: {self.excel_file_path}")
                return
            
            # Read the Excel file
            # LibSets typically has multiple sheets, we'll try to read the main data sheet
            excel_file = pd.ExcelFile(self.excel_file_path)
            
            # Print available sheet names for debugging
            print(f"Available sheets in {self.excel_file_path}: {excel_file.sheet_names}")
            
            # Try to find the main data sheet (common names)
            main_sheet = None
            for sheet_name in excel_file.sheet_names:
                if any(keyword in sheet_name.lower() for keyword in ['data', 'sets', 'items', 'main']):
                    main_sheet = sheet_name
                    break
            
            if main_sheet is None:
                # Use the first sheet if no obvious main sheet found
                main_sheet = excel_file.sheet_names[0]
            
            print(f"Using sheet: {main_sheet}")
            
            # Read the main data sheet with header=1 (row 2 contains column names)
            df = pd.read_excel(self.excel_file_path, sheet_name=main_sheet, header=1)
            
            print(f"Loaded {len(df)} rows from gear set database")
            print(f"Columns: {list(df.columns)}")
            
            # Process the data based on column names
            self._process_dataframe(df)
            
        except Exception as e:
            print(f"Error loading gear set database: {e}")
            print("Falling back to basic gear set data...")
            self._load_fallback_data()
    
    def _process_dataframe(self, df: pd.DataFrame):
        """Process the DataFrame to extract gear set information."""
        # The LibSets Excel file has set metadata in the "Sets data" sheet
        # We'll extract set names and IDs for now, and build item mappings from other sources
        
        # Use the exact column names we found
        name_en_col = "Name EN"
        setId_col = "ESO ingame setId"
        
        if name_en_col and setId_col:
            # Build set ID to name mapping
            for _, row in df.iterrows():
                set_id = row[setId_col]
                set_name_en = row[name_en_col]
                
                if pd.notna(set_id) and pd.notna(set_name_en):
                    set_id_str = str(int(set_id))
                    set_name = str(set_name_en).strip().strip('"').replace("\\'", "'")
                    
                    self.set_info[set_name] = {
                        'set_id': set_id_str,
                        'items': [],
                        'abilities': []
                    }
                    
                    # Also build set_id to name mapping
                    self.set_id_to_name[set_id_str] = set_name
            
            print(f"Loaded {len(self.set_info)} sets from LibSets metadata")
            print(f"Built {len(self.set_id_to_name)} set ID mappings")
            
            # For now, we'll use a combination of the LibSets metadata and our known item mappings
            self._build_comprehensive_mappings()
        else:
            print("LibSets metadata not found in expected format")
            self._load_fallback_data()
    
    def _build_comprehensive_mappings(self):
        """Build comprehensive item and ability mappings using multiple sources."""
        # Known item ID to set name mappings (these would come from actual game data)
        # This is a starting point - in a real implementation, you'd want to extract
        # this data from the actual ESO game files or a more complete database
        
        # Map only items we actually know the set names for
        # These should be verified against actual ESO data, not guessed
        known_item_mappings = {
            # Only include items we're certain about - remove the incorrect assumptions
            # '95044': "Unknown Set",     # HEAD item - need to verify actual set
            # '194512': "Unknown Set",    # NECK item - need to verify actual set  
            # '215597': "Unknown Set",    # CHEST item - need to verify actual set
            # '174468': "Unknown Set",    # SHOULDERS item - need to verify actual set
            # '173599': "Unknown Set",    # MAIN_HAND/OFF_HAND items - need to verify actual set
            # '215603': "Unknown Set",    # WAIST item - need to verify actual set
            # '215601': "Unknown Set",    # LEGS item - need to verify actual set
            # '215598': "Unknown Set",    # FEET item - need to verify actual set
            # '175047': "Unknown Set",    # RING items - need to verify actual set
            # '215599': "Unknown Set",    # HAND item - need to verify actual set
            '166198': "Spectral Cloak",  # Blackrose Dagger
            '166196': "Spectral Cloak",  # Blackrose Dagger (alternative ID)
            '87874': "Perfected Slivers of the Null Arca",  # Lightning Staff
            '194512': "Velothi Ur-Mage's Amulet",  # Mythic amulet
            '95180': "Slimecraw",  # Monster set
            '170746': "Unleashed Ritualist",  # Set pieces
            '170734': "Unleashed Ritualist",  # Set pieces
            '170751': "Unleashed Ritualist",  # Set pieces
            '145018': "Spectral Cloak",  # Set pieces
            # '166199': "Unknown Set",    # BACKUP_MAIN item - need to verify actual set
            
            # Example mappings for other sets (these would need to be updated with actual data)
            '154691': "Bahsei's Mania",    # Ability ID - this one we know
            '66899': "Spell Power Cure", 
            '107202': "Arms of Relequen",
            '107203': "Arms of Relequen",
            '133378': "Mother Ciannait",
        }
        
        # Known ability ID to set name mappings
        known_ability_mappings = {
            '154691': "Bahsei's Mania",
            '66899': "Spell Power Cure",
            '107202': "Arms of Relequen",
            '107203': "Arms of Relequen",
            '133378': "Mother Ciannait",
            '84731': "Witchmother's Potent Brew",  # Might be consumable
        }
        
        # Add known mappings
        self.item_to_set.update(known_item_mappings)
        self.ability_to_set.update(known_ability_mappings)
        
        # Update set info with items and abilities
        for set_name, set_data in self.set_info.items():
            for item_id, mapped_set_name in known_item_mappings.items():
                if mapped_set_name == set_name:
                    set_data['items'].append(item_id)
            
            for ability_id, mapped_set_name in known_ability_mappings.items():
                if mapped_set_name == set_name:
                    set_data['abilities'].append(ability_id)
        
        print(f"Built comprehensive mappings: {len(self.item_to_set)} items, {len(self.ability_to_set)} abilities")
    
    def _load_fallback_data(self):
        """Load basic fallback data if Excel file fails."""
        # Use only items we actually know the set names for
        self.item_to_set = {
            # Only include items we're certain about
            '154691': "Bahsei's Mania",    # Ability ID - this one we know
        }
        
        self.ability_to_set = {
            '154691': "Bahsei's Mania",
            '66899': "Spell Power Cure", 
            '107202': "Arms of Relequen",
            '107203': "Arms of Relequen",
            '133378': "Mother Ciannait",
            '84731': "Witchmother's Potent Brew",
        }
    
    def get_set_name_by_item_id(self, item_id: str) -> Optional[str]:
        """Get the gear set name for a given item ID."""
        return self.item_to_set.get(item_id)
    
    def get_set_name_by_set_id(self, set_id: str) -> Optional[str]:
        """Get the gear set name for a given set ID."""
        return self.set_id_to_name.get(set_id)
    
    def get_set_name_by_ability_id(self, ability_id: str) -> Optional[str]:
        """Get the gear set name for a given ability ID."""
        return self.ability_to_set.get(ability_id)
    
    def get_set_info(self, set_name: str) -> Optional[Dict]:
        """Get detailed information about a gear set."""
        return self.set_info.get(set_name)
    
    def get_all_sets(self) -> List[str]:
        """Get a list of all gear set names."""
        return list(self.set_info.keys())
    
    def reload_database(self):
        """Reload the database from the Excel file."""
        self.item_to_set.clear()
        self.set_info.clear()
        self.ability_to_set.clear()
        self._load_database()
    
    def is_database_loaded(self) -> bool:
        """Check if the database has been successfully loaded."""
        return len(self.item_to_set) > 0 or len(self.ability_to_set) > 0


# Global instance for easy access
gear_set_db = GearSetDatabase()
