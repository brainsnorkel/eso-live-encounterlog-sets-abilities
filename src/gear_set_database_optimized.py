"""
Optimized Gear Set Database Module

This module provides fast gear set lookups using pre-generated data structures
instead of parsing Excel files at runtime. The data is generated from LibSets_SetData.xlsm
during the build process.
"""

from typing import Dict, List, Optional
from gear_set_data import (
    SET_ID_TO_NAME, SET_NAME_TO_ID, SET_INFO,
    KNOWN_ITEM_MAPPINGS, KNOWN_ABILITY_MAPPINGS,
    get_set_name_by_id, get_set_id_by_name, get_set_info,
    get_set_name_by_item_id, get_set_name_by_ability_id,
    get_stats
)

class OptimizedGearSetDatabase:
    """
    Optimized gear set database using pre-generated data structures.
    
    This class provides the same interface as the original GearSetDatabase
    but uses pre-generated Python data instead of Excel file parsing.
    """
    
    def __init__(self):
        """Initialize the optimized gear set database."""
        self.item_to_set = KNOWN_ITEM_MAPPINGS.copy()
        self.ability_to_set = KNOWN_ABILITY_MAPPINGS.copy()
        self.set_id_to_name = SET_ID_TO_NAME.copy()
        self.set_name_to_id = SET_NAME_TO_ID.copy()
        self.set_info = SET_INFO.copy()
        
        # Load statistics
        self.stats = get_stats()
    
    def get_set_name_by_item_id(self, item_id: str) -> Optional[str]:
        """Get the gear set name for a given item ID."""
        return get_set_name_by_item_id(item_id)
    
    def get_set_name_by_ability_id(self, ability_id: str) -> Optional[str]:
        """Get the gear set name for a given ability ID."""
        return get_set_name_by_ability_id(ability_id)
    
    def get_set_name_by_set_id(self, set_id: str) -> Optional[str]:
        """Get the gear set name for a given set ID."""
        return get_set_name_by_id(set_id)
    
    def get_set_id_by_name(self, set_name: str) -> Optional[str]:
        """Get the set ID for a given gear set name."""
        return get_set_id_by_name(set_name)
    
    def get_set_info(self, set_name: str) -> Optional[Dict]:
        """Get detailed information about a gear set."""
        return get_set_info(set_name)
    
    def is_database_loaded(self) -> bool:
        """Check if the database has been successfully loaded."""
        return len(self.set_id_to_name) > 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        return get_stats()
    
    def reload_database(self):
        """Reload the database (no-op for pre-generated data)."""
        print("Database is pre-generated - no reload needed")
    
    def get_all_set_names(self) -> List[str]:
        """Get all gear set names."""
        return list(self.set_name_to_id.keys())
    
    def get_all_set_ids(self) -> List[str]:
        """Get all gear set IDs."""
        return list(self.set_id_to_name.keys())

# Global instance for easy access
gear_set_db = OptimizedGearSetDatabase()
