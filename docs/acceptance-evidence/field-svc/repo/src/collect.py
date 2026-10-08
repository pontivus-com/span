"""Collect field readings and limits from sensors."""

from buffer import hold
from ship import send


def collect(sensor):
    reading = sensor.read()
    hold(reading)
    send(reading)
