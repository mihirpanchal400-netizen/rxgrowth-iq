"""Claude narrative layer.

The model reads numbers only through typed tools and never receives raw data. Every
generated narrative is verified numeral-by-numeral against the tool responses before
it is returned. See docs/compliance.md section 6.
"""
