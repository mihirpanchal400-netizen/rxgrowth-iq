"""Data access, one class per aggregate.

Prescriber display suppression is enforced here rather than in the UI, so that a new
endpoint cannot accidentally leak an opted-out prescriber. See docs/compliance.md
section 3.
"""
