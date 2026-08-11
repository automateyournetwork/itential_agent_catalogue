from utils.formatting import format_bytes


def test_format_bytes():
    assert format_bytes(500) == "500.0B"
    assert format_bytes(2048) == "2.0KB"
