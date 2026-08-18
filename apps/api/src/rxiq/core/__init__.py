"""Pure metric engine.

Everything in this package is a pure function: primitives and frames in, values out.
No database, no HTTP, no clock reads, no configuration lookups at call time.

That constraint is what makes the domain math auditable. The growth-decomposition
identity can be asserted across thousands of Hypothesis-generated inputs only because
these functions have no environment to stub. See docs/ADR/0001-architecture.md.

``mypy`` is configured to reject explicit ``Any`` in this package specifically.
"""
