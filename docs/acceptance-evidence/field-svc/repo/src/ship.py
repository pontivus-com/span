"""Send held readings downstream."""

from failures import dead_letter


def send(reading):
    try:
        transmit(reading)
    except IOError:
        dead_letter(reading)
