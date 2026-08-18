#!/usr/bin/env python3
"""Block real prescriber or licensed vendor data from entering the repository.

Implements the enforcement half of ``docs/compliance.md`` section 1.

Licensed prescription data (IQVIA, Symphony Health, Komodo, and similar) is bound by
data-use agreements that prohibit storage outside the licensee's environment. This
repository is public and git history is permanent, so the accident must be made
impossible rather than merely discouraged.

The scanner reads the **diff**, not the working tree. It stays fast, and an
allowlisted fixture does not get re-flagged on every subsequent PR.

Detections
----------
1. **Real-looking NPIs** -- 10 digits that begin with 1 or 2 and pass the CMS check-digit
   algorithm (Luhn over ``80840`` + the first nine digits). Synthetic NPIs in this project
   begin with ``9``, which CMS has never issued, so they cannot collide.
2. **Real-looking DEA numbers** -- two letters followed by seven digits that satisfy the
   DEA checksum.
3. **Vendor filenames** -- file *names* matching known licensed-extract patterns. Matched
   on paths only, never on content, so prose in ``docs/compliance.md`` naming those
   vendors does not trip the gate.
4. **Bulk data files** -- added files with a data extension above a size threshold.

Exit codes: ``0`` clean, ``1`` findings, ``2`` invocation error.

Stdlib only -- this must run before dependencies are installed.

.. note::
   This file is **intentionally self-allowlisted**. Defining ``ALLOWLIST_MARKER`` below
   places the marker string in the file, which exempts it from its own scan. That is
   required: the self-tests contain valid specimen NPI and DEA identifiers, and a scanner
   that flagged its own fixtures could never pass CI. The specimens are textbook
   check-digit examples, not registrant records.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Files carrying this marker are exempt. Reserve it for reviewed synthetic fixtures and
#: for this scanner's own tests, which necessarily contain valid specimen identifiers.
ALLOWLIST_MARKER = "rxiq:synthetic-data-ok"

#: Synthetic NPIs must start with this digit. CMS issues 1 and 2; 3-9 have never been
#: allocated, so a leading 9 can never collide with a real registrant.
SYNTHETIC_NPI_PREFIX = "9"

#: Prefix CMS specifies for the NPI check-digit calculation.
_NPI_LUHN_PREFIX = "80840"

#: Leading digits CMS actually issues.
_REAL_NPI_LEADING = ("1", "2")

MAX_DATA_FILE_BYTES = 512 * 1024

DATA_EXTENSIONS = frozenset(
    {".csv", ".tsv", ".parquet", ".xlsx", ".xls", ".sas7bdat", ".dta", ".sav", ".dbf"}
)

#: Substrings that identify a licensed extract by filename. Deliberately specific --
#: a bare "ims" or "sha" would fire on unrelated files.
VENDOR_FILENAME_PATTERNS: tuple[str, ...] = (
    "xponent",
    "plantrak",
    "dddx",
    "iqvia",
    "symphony_health",
    "symphonyhealth",
    "komodo",
    "ims_health",
    "imshealth",
    "apld",
    "laad",
    "definitive_healthcare",
    "prescriber_level",
    "rx_extract",
)

#: Bounded on both sides so a 12-digit number is not read as a 10-digit one.
_NPI_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")

#: Second character may be a digit; DEA issues numeric second characters in some series.
_DEA_RE = re.compile(r"(?<![A-Z0-9])([A-Z][A-Z0-9])(\d{7})(?![A-Z0-9])")


# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------


def _luhn_ok(digits: str) -> bool:
    """Standard Luhn check over a digit string that includes its check digit."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def is_real_looking_npi(candidate: str) -> bool:
    """True if ``candidate`` could be a genuine CMS-issued NPI.

    An NPI is ten digits validated by Luhn over ``80840`` plus its first nine digits.
    We additionally require a leading 1 or 2, the only ranges CMS has issued, so that
    synthetic identifiers beginning with 9 are structurally incapable of matching.

    >>> is_real_looking_npi("1234567893")
    True
    >>> is_real_looking_npi("9234567893")   # synthetic range
    False
    >>> is_real_looking_npi("1234567890")   # bad check digit
    False
    """
    if len(candidate) != 10 or not candidate.isdigit():
        return False
    if candidate[0] not in _REAL_NPI_LEADING:
        return False
    return _luhn_ok(_NPI_LUHN_PREFIX + candidate)


def is_real_looking_dea(letters: str, digits: str) -> bool:
    """True if a two-letter/seven-digit token satisfies the DEA checksum.

    Checksum: (d1 + d3 + d5) + 2 * (d2 + d4 + d6) must end in d7.

    >>> is_real_looking_dea("AB", "1234563")
    True
    >>> is_real_looking_dea("AB", "1234567")
    False
    """
    if len(digits) != 7 or not digits.isdigit():
        return False
    odd = int(digits[0]) + int(digits[2]) + int(digits[4])
    even = int(digits[1]) + int(digits[3]) + int(digits[5])
    return (odd + 2 * even) % 10 == int(digits[6])


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    detail: str
    remedy: str

    def render(self) -> str:
        return (
            f"  {self.path}\n"
            f"    {self.kind}: {self.detail}\n"
            f"    -> {self.remedy}"
        )


def scan_added_line(path: str, line: str) -> list[Finding]:
    """Scan a single added diff line for real-looking identifiers."""
    findings: list[Finding] = []

    for match in _NPI_RE.finditer(line):
        candidate = match.group(1)
        if is_real_looking_npi(candidate):
            findings.append(
                Finding(
                    path=path,
                    kind="Real-looking NPI",
                    detail=f"{candidate[:3]}***{candidate[-2:]} passes the CMS check digit",
                    remedy=(
                        f"Synthetic NPIs must begin with {SYNTHETIC_NPI_PREFIX!r}. "
                        "Regenerate via packages/synth."
                    ),
                )
            )

    for match in _DEA_RE.finditer(line):
        letters, digits = match.group(1), match.group(2)
        if is_real_looking_dea(letters, digits):
            findings.append(
                Finding(
                    path=path,
                    kind="Real-looking DEA number",
                    detail=f"{letters}{digits[:2]}***** satisfies the DEA checksum",
                    remedy="Remove it. DEA numbers are not modelled in this schema.",
                )
            )

    return findings


def scan_path(path: str, size_bytes: int | None) -> list[Finding]:
    """Scan a file path for vendor-extract naming and bulk-data red flags."""
    findings: list[Finding] = []
    lowered = path.lower()

    for pattern in VENDOR_FILENAME_PATTERNS:
        if pattern in lowered:
            findings.append(
                Finding(
                    path=path,
                    kind="Licensed vendor filename",
                    detail=f"path contains {pattern!r}",
                    remedy=(
                        "Licensed extracts must never leave the licensee environment. "
                        "See docs/compliance.md section 1."
                    ),
                )
            )
            break

    suffix = Path(path).suffix.lower()
    if suffix in DATA_EXTENSIONS and size_bytes is not None and size_bytes > MAX_DATA_FILE_BYTES:
        findings.append(
            Finding(
                path=path,
                kind="Bulk data file",
                detail=f"{suffix} file of {size_bytes // 1024} KiB exceeds the "
                f"{MAX_DATA_FILE_BYTES // 1024} KiB limit",
                remedy=(
                    "Generate data at build time via packages/synth rather than "
                    "committing it."
                ),
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _is_allowlisted(path: str) -> bool:
    """True if the file carries the exemption marker."""
    try:
        return ALLOWLIST_MARKER in Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return False


def _file_size(path: str) -> int | None:
    try:
        return Path(path).stat().st_size
    except OSError:
        return None


def scan_diff(base: str, head: str) -> list[Finding]:
    """Scan every line added between ``base`` and ``head``."""
    findings: list[Finding] = []
    current_path: str | None = None
    skip_current = False

    diff = _git("diff", "--unified=0", "--no-color", f"{base}...{head}")

    for line in diff.splitlines():
        if line.startswith("+++ "):
            raw = line[4:].strip()
            if raw == "/dev/null":
                current_path, skip_current = None, True
                continue
            current_path = raw[2:] if raw.startswith("b/") else raw
            skip_current = _is_allowlisted(current_path)
            if not skip_current:
                findings.extend(scan_path(current_path, _file_size(current_path)))
            continue

        if line.startswith("+") and not line.startswith("+++"):
            if current_path and not skip_current:
                findings.extend(scan_added_line(current_path, line[1:]))

    return findings


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


class SelfTest(unittest.TestCase):
    """Runs in CI via ``--self-test``. Migrates to pytest once Phase 0 issue #2 lands."""

    def test_valid_npi_is_flagged(self) -> None:
        self.assertTrue(is_real_looking_npi("1234567893"))
        self.assertTrue(is_real_looking_npi("1245319599"))

    def test_synthetic_prefix_is_never_flagged(self) -> None:
        # Every 9-prefixed identifier the generator can emit must pass through.
        for tail in range(0, 1000):
            npi = f"9{tail:09d}"
            self.assertFalse(is_real_looking_npi(npi), npi)

    def test_bad_check_digit_is_not_flagged(self) -> None:
        self.assertFalse(is_real_looking_npi("1234567890"))

    def test_wrong_length_is_not_flagged(self) -> None:
        self.assertFalse(is_real_looking_npi("123456789"))
        self.assertFalse(is_real_looking_npi("12345678930"))

    def test_npi_not_matched_inside_longer_digit_run(self) -> None:
        self.assertEqual(scan_added_line("f.py", "x = 123456789312345"), [])

    def test_dea_checksum(self) -> None:
        self.assertTrue(is_real_looking_dea("AB", "1234563"))
        self.assertFalse(is_real_looking_dea("AB", "1234567"))

    def test_line_scan_flags_npi(self) -> None:
        found = scan_added_line("seed.py", 'prescriber = "1234567893"')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "Real-looking NPI")

    def test_finding_does_not_echo_full_identifier(self) -> None:
        # The scanner must not reprint a real identifier into public CI logs.
        found = scan_added_line("seed.py", 'npi = "1234567893"')
        self.assertNotIn("1234567893", found[0].detail)

    def test_vendor_filename_flagged(self) -> None:
        found = scan_path("data/xponent_2026_q1.txt", None)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "Licensed vendor filename")

    def test_ordinary_path_is_clean(self) -> None:
        self.assertEqual(scan_path("apps/api/src/rxiq/core/metrics.py", 1024), [])

    def test_bulk_data_file_flagged(self) -> None:
        found = scan_path("fixtures/big.csv", MAX_DATA_FILE_BYTES + 1)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "Bulk data file")

    def test_small_fixture_csv_allowed(self) -> None:
        self.assertEqual(scan_path("tests/fixtures/golden.csv", 2048), [])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main", help="base ref (default: origin/main)")
    parser.add_argument("--head", default="HEAD", help="head ref (default: HEAD)")
    parser.add_argument("--self-test", action="store_true", help="run the scanner's own tests")
    args = parser.parse_args(argv)

    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelfTest)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    try:
        findings = scan_diff(args.base, args.head)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not findings:
        print(f"OK: no real-data indicators in {args.base}...{args.head}")
        return 0

    print(f"\nBLOCKED: {len(findings)} real-data indicator(s) found.\n")
    for finding in findings:
        print(finding.render())
    print(
        "\nThis repository is public and git history is permanent. See docs/compliance.md\n"
        f"section 1. If this is a reviewed synthetic fixture, add the marker\n"
        f"  {ALLOWLIST_MARKER}\n"
        "to the file and explain the exemption in the PR description.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
