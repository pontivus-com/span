"""Hold readings until shipped."""

STOCK = {}


def hold(reading):
    STOCK[reading.key] = reading
