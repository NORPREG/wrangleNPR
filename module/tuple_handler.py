from collections import Counter

# ============================================================================
# TUPLE_KEY utilities
# ============================================================================

TUPLE_KEY = ["kno", "refvolumid", "planuid"]


def make_tuple_key(row, key_names=TUPLE_KEY):
    """Convert a row (dict) to a normalized tuple key using specified field names."""
    return tuple(str(row.get(k, "")) for k in key_names)


def count_tuple_keys(rows, key_names=TUPLE_KEY):
    """Count occurrences of each tuple key across rows."""
    return Counter(make_tuple_key(row, key_names) for row in rows)


def find_duplicate_tuple_keys(rows, key_names=TUPLE_KEY):
    """Return set of tuple keys that appear more than once."""
    counts = count_tuple_keys(rows, key_names)
    return {k for k, c in counts.items() if c > 1}


def build_key_lookup(rows, skip_keys=None, key_names=TUPLE_KEY):
    """Build a dict mapping tuple keys to records (first occurrence wins for duplicates).
    Rows whose key appears in skip_keys are excluded."""
    lookup = {}
    for row in rows:
        key = make_tuple_key(row, key_names)
        if skip_keys and key in skip_keys:
            continue
        if key not in lookup:
            lookup[key] = row
    return lookup
