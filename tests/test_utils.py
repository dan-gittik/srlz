from srlz.utils import concat


def test_concat_none() -> None:
    for empty in ([], set(), (i for i in range(1, 1))):
        assert concat(empty) == "<none>"


def test_concat_one() -> None:
    for one in ([1], {1}, (i for i in range(1, 2))):
        assert concat(one) == "1"


def test_concat_two() -> None:
    for two in ([1, 2], {1, 2}, (i for i in range(1, 3))):
        assert concat(two) == "1 and 2"


def test_concat_many() -> None:
    for many in ([1, 2, 3], {1, 2, 3}, (i for i in range(1, 4))):
        assert concat(many) == "1, 2 and 3"
