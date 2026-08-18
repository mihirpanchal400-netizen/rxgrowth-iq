"""Synthetic pharmaceutical market generator.

The only source of data in this repository. Emits NPIs in the 9-prefix range, which
CMS has never issued, so synthetic identifiers cannot collide with real registrants.
See docs/compliance.md section 1.
"""

__version__ = "0.1.0"

#: Leading digit reserved for synthetic NPIs. Asserted by scripts/check_no_real_data.py.
SYNTHETIC_NPI_PREFIX = "9"
