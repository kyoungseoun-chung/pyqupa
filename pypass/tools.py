#!/usr/bin/env python3
"""Useful tools."""

import numpy as np

from typing import Optional


def hex_to_rgb(hex: str, opacity: Optional[int] = None) -> list[int, int, int]:
    """Convert hex code to rgb"""
    hex = hex.lstrip("#")
    if opacity is not None:
        rgba = []
        for i in (0, 2, 4):
            rgba.append(int(hex[i : i + 2], 16))
        rgba.append(int(opacity * 255))
        return rgba
    else:
        return list(int(hex[i : i + 2], 16) for i in (0, 2, 4))


def decompose_digit(num: float, padding: int) -> tuple[float, float, int]:
    """Decompose the given number.

    Note:
        - if `order > 2`, leading digits are the first two digits and ceil the second digit.

    >>> num = 635
    >>> print(decompose_digit(num))
    (600, 6, 2)
    >>> num = 2635
    >>> print(decompose_digit(num))
    (27, 2700, 3)

    Args:
        num (float): number to be decomposed
    """

    order = int(np.log10(num))

    first_digit = num // 10 ** (order - 1)
    drop_remaining = (first_digit + padding) * 10 ** (order - 1)

    return drop_remaining, first_digit, order
