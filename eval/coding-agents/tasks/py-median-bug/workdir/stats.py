"""Small statistics helpers."""


def median(xs):
    """Return the median of a non-empty list of numbers.

    BUG: for an even-length list this returns the lower of the two middle
    values instead of their average.
    """
    if not xs:
        raise ValueError("median() of empty sequence")
    s = sorted(xs)
    mid = len(s) // 2
    return s[mid]
