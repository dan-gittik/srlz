from typing import Any, Iterable


def concat(iterable: Iterable[Any]) -> str:
    """
    Concatenate items into a string.

        >>> and_([])
        '<none>'
        >>> and_([1])
        '1'
        >>> and_([1, 2])
        '1 and 2'
        >>> and_([1, 2, 3])
        '1, 2 and 3'

    Arguments:
        iterable: The items to concatenate.

    Returns:
        A string of the concatenated items.
    """
    items = sorted(iterable)
    if not items:
        return "<none>"
    if len(items) == 1:
        return str(items[0])
    if len(items) == 2:
        return f"{str(items[0])} and {str(items[1])}"
    return ", ".join(map(str, items[:-1])) + " and " + str(items[-1])
