import re
from django.db import models


class SKUGenerator:

    #Finished product category codes
    FG_CATEGORY_CODES = {
        "meat_pie": "MPI",
        "sausage_roll": "SRL",
        "pastry": "PST",
        "tart": "TRT",
        "croissant": "CRS",
        "danish": "DAN",
        "scone": "SCN",
        "savory_roll": "SVR",
    }

    # Raw material category codes
    RM_CATEGORY_CODES = {
        "flour": "FLR",
        "sugar": "SGR",
        "butter": "BTR",
        "yeast": "YST",
        "egg": "EGG",
        "milk": "MLK",
        "meat": "MET",
        "oil": "OIL",
        "salt": "SLT",
        "spice_mix": "SPC",
    }

    # Packaging material category codes
    PK_CATEGORY_CODES = {
        "box": "BOX",
        "bag": "BAG",
        "wrapper": "WRP",
        "tray": "TRY",
        "label": "LBL",
    }

    CATEGORY_CODES = {**FG_CATEGORY_CODES, **RM_CATEGORY_CODES, **PK_CATEGORY_CODES}
    
    UNIT_CODES = {
        "kg": "KG",
        "g": "GR",
        "l": "LT",
        "ml": "ML",
        "pieces": "PC",
        "dozen": "DZ",
        "box": "BX",
    }

    @classmethod
    def generate_sku(cls, name, category=None, unit_of_measure=None):
        """Generate SKU in format: CAT-NAME-UOM-SEQ"""

        # Get category code
        cat_code = cls._get_category_code(category, name)

        # Get name code (first 4 chars of cleaned name)
        name_code = cls._get_name_code(name)

        # Get unit code
        unit_code = cls._get_unit_code(unit_of_measure)

        # Get next sequence number
        seq_num = cls._get_next_sequence(cat_code, name_code, unit_code)

        return f"{cat_code}-{name_code}-{unit_code}-{seq_num:03d}"

    @classmethod
    def _get_category_code(cls, category, name):
        """Get 3-char category code"""
        if category:
            category_lower = category.lower().strip()
            if category_lower in cls.CATEGORY_CODES:
                return cls.CATEGORY_CODES[category_lower]

        # Fallback: detect from name
        name_lower = name.lower()
        for cat, code in cls.CATEGORY_CODES.items():
            if cat in name_lower:
                return code

        return "GEN"  # Generic

    @classmethod
    def _get_name_code(cls, name):
        """Get 4-char name code from product name"""
        # Remove special chars, keep only alphanumeric
        clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
        # Take first 4 chars of first word, uppercase
        words = clean_name.split()
        if words:
            return words[0][:4].upper().ljust(4, "X")
        return "PROD"

    @classmethod
    def _get_unit_code(cls, unit_of_measure):
        """Get 2-char unit code"""
        if unit_of_measure and unit_of_measure in cls.UNIT_CODES:
            return cls.UNIT_CODES[unit_of_measure]
        return "PC"  # Default to pieces

    @classmethod
    def _get_next_sequence(cls, cat_code, name_code, unit_code):
        """Get next sequence number for this SKU pattern"""
        from central.models import Product

        prefix = f"{cat_code}-{name_code}-{unit_code}-"

        # Find highest existing sequence number
        existing_skus = Product.objects.filter(sku__startswith=prefix).values_list(
            "sku", flat=True
        )

        max_seq = 0
        for sku in existing_skus:
            try:
                seq_part = sku.split("-")[-1]
                seq_num = int(seq_part)
                max_seq = max(max_seq, seq_num)
            except (ValueError, IndexError):
                continue

        return max_seq + 1
