"""
Gear set database: set lookups over the generated LibSets data.

The data lives in gear_set_data.py, which scripts/generate_gear_data.py writes
from data/gear_sets/LibSets_SetData.xlsm. Nothing is parsed at runtime.
"""

from typing import Dict, Optional
from gear_set_data import (
    SET_ID_TO_NAME, SET_NAME_TO_ID, SET_INFO,
    KNOWN_ITEM_MAPPINGS, KNOWN_ABILITY_MAPPINGS,
    get_set_name_by_id, get_set_id_by_name, get_set_info,
    get_set_name_by_item_id, get_set_name_by_ability_id,
    get_stats
)

class GearSetDatabase:
    """Set names, ids and details, looked up in the generated data."""

    def __init__(self):
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

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        return get_stats()


# Global instance for easy access
gear_set_db = GearSetDatabase()
