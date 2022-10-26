#!/usr/bin/env python3
"""Useful tools."""
from typing import Optional

import numpy as np
import requests
from lxml import html
from rich.console import Console
from rich.progress import Progress

console = Console()
rprint = console.print

progress = Progress()


def translate(
    target: str, from_lang: str = "auto", to_lang: str = "auto"
) -> str:
    """Returns the translation using google translate
    Please define `from_lang` and `to_lang` with iso code.
    (French = fr, English = en, Spanish = es, etc...)
    if not defined it will detect it or use english by default
    """
    link = (
        f"http://translate.google.com/m?tl={to_lang}&sl={from_lang}&q={target}"
    )

    page = requests.get(link)
    tree = html.fromstring(page.content)
    return tree.xpath('//div[@class="result-container"]/text()')[0]


def system_logger(
    prefix: str, msg: str, values: Optional[float] = None
) -> None:
    """Pretty logger using rich."""

    if values is None:
        console.print(f"[bold blue]{prefix.upper()}[/bold blue]: " + msg)
    else:
        console.print(
            f"[bold blue]{prefix.upper()}[/bold blue]: "
            + msg
            + f"[bold magenta] - {values} [/bold magenta]"
        )


def hex_to_rgb(hex: str, opacity: Optional[float] = None) -> list[int]:
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
