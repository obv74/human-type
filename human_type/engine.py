"""Human-like typing: keyboard geometry, word chunks, realistic slips."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .keyboard import Keyboard, tiny_settle

NEIGHBORS = {
    "a": "sqwz",
    "b": "vghn",
    "c": "xdfv",
    "d": "sfcerx",
    "e": "wrsdf",
    "f": "dgcrtv",
    "g": "fhtbvy",
    "h": "gjnybu",
    "i": "ujko",
    "j": "hkmnui",
    "k": "jloim",
    "l": "kop",
    "m": "njk",
    "n": "bhjm",
    "o": "iklp",
    "p": "ol",
    "q": "wa",
    "r": "edft",
    "s": "awedxz",
    "t": "rfgy",
    "u": "yhji",
    "v": "cfgb",
    "w": "qase",
    "x": "zsdc",
    "y": "tghu",
    "z": "asx",
    "1": "2q",
    "2": "13qw",
    "3": "24we",
    "4": "35er",
    "5": "46rt",
    "6": "57ty",
    "7": "68yu",
    "8": "79ui",
    "9": "80io",
    "0": "9op",
}

# QWERTY key centers in key-width units, plus which finger types them.
# 0–3 left pinky→index, 4–7 right index→pinky, -1 thumbs.
KEY_POS: dict[str, tuple[float, float]] = {}
FINGER: dict[str, int] = {}


def _layout_row(keys: str, x0: float, y: float, fingers: list[int]) -> None:
    for i, char in enumerate(keys):
        KEY_POS[char] = (x0 + i, y)
        if i < len(fingers):
            FINGER[char] = fingers[i]


_layout_row("1234567890", 0.0, 0.0, [0, 1, 2, 3, 3, 4, 4, 5, 6, 7])
_layout_row("qwertyuiop", 0.5, 1.0, [0, 1, 2, 3, 3, 4, 4, 5, 6, 7])
_layout_row("asdfghjkl", 0.75, 2.0, [0, 1, 2, 3, 3, 4, 4, 5, 6])
_layout_row("zxcvbnm", 1.25, 3.0, [0, 1, 2, 3, 4, 4, 5])
KEY_POS.update({"-": (10.0, 0.0), "=": (11.0, 0.0), "[": (10.5, 1.0), "]": (11.5, 1.0)})
KEY_POS.update({";": (9.75, 2.0), "'": (10.75, 2.0), ",": (8.25, 3.0), ".": (9.25, 3.0), "/": (10.25, 3.0)})
KEY_POS[" "] = (5.0, 4.0)
FINGER[" "] = -1

COMMON_WORDS = {
    "a", "i", "to", "of", "in", "it", "on", "is", "as", "at", "be", "or", "an",
    "if", "so", "we", "he", "my", "me", "do", "no", "up", "by", "the", "and",
    "that", "have", "for", "not", "with", "you", "this", "but", "his", "from",
    "they", "say", "her", "she", "will", "one", "all", "would", "there", "their",
    "what", "out", "about", "who", "get", "which", "when", "make", "can", "like",
    "time", "just", "him", "know", "take", "into", "year", "your", "some", "could",
    "them", "see", "other", "than", "then", "now", "look", "only", "come", "its",
    "over", "think", "also", "back", "after", "use", "two", "how", "our", "work",
    "first", "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "was", "are", "been", "has", "had", "did",
    "were", "said", "each", "more", "very", "here", "many", "where",
}


@dataclass
class TypeSettings:
    wpm: int = 62
    humanize: float = 0.7  # 0 = even, 1 = very human
    typos: bool = True


@dataclass
class TypeProgress:
    index: int
    total: int
    done: bool = False
    stopped: bool = False


class HumanTyper:
    def __init__(self, keyboard: Keyboard) -> None:
        self.keyboard = keyboard
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def type_text(
        self,
        text: str,
        settings: TypeSettings,
        on_progress: Optional[Callable[[TypeProgress], None]] = None,
        start_at: int = 0,
    ) -> TypeProgress:
        self._stop = False
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        total = len(text)
        start_at = max(0, min(start_at, total))
        remaining = text[start_at:]
        human = max(0.0, min(1.0, settings.humanize))
        typo_rate = (0.018 * human) if settings.typos else 0.0
        delays = _plan_delays(remaining, settings)
        overhead = 0.008

        if on_progress and start_at:
            on_progress(TypeProgress(index=start_at, total=total))

        for offset, char in enumerate(remaining):
            i = start_at + offset
            if self._stop:
                progress = TypeProgress(index=i, total=total, stopped=True)
                if on_progress:
                    on_progress(progress)
                return progress

            time.sleep(max(0.0, delays[offset] - overhead))

            nxt = text[i + 1] if i + 1 < total else ""
            if typo_rate > 0 and char.isalpha() and i > 0 and random.random() < typo_rate:
                _slip(self.keyboard, char, nxt, human)

            self.keyboard.write(char)
            tiny_settle()

            if on_progress:
                on_progress(TypeProgress(index=i + 1, total=total))

        progress = TypeProgress(index=total, total=total, done=True)
        if on_progress:
            on_progress(progress)
        return progress


def estimate_seconds(text: str, settings: TypeSettings) -> float:
    chars = max(1, len(text))
    return chars * 60.0 / (max(20, settings.wpm) * 5.0)


def _plan_delays(text: str, settings: TypeSettings) -> list[float]:
    """Per-character waits that still average to the selected WPM."""
    n = len(text)
    if n == 0:
        return []
    human = max(0.0, min(1.0, settings.humanize))
    mean = 60.0 / (max(20, settings.wpm) * 5.0)
    if human <= 0.02:
        return [mean] * n

    word_factor = _word_factors(text)
    weights: list[float] = []
    burst_left = 0
    since_pause = 0
    prev = ""
    for i, char in enumerate(text):
        if burst_left <= 0 and human > 0.15 and random.random() < 0.10 * human:
            burst_left = random.randint(3, 7)
        weight = random.gauss(1.0, 0.10 + 0.38 * human)
        weight = max(0.32, min(2.2, weight))
        if burst_left > 0:
            burst_left -= 1
            weight *= random.uniform(0.50, 0.78)
        travel = _travel(prev, char)
        weight *= 1.0 + (travel - 1.0) * human
        weight *= 1.0 + (word_factor[i] - 1.0) * human
        if prev in ".!?":
            weight *= 1.0 + 1.05 * human
        elif prev in ",;:":
            weight *= 1.0 + 0.40 * human
        elif prev == " ":
            weight *= 1.0 + 0.12 * human
        if char.isupper() and char.isalpha():
            weight *= 1.0 + 0.16 * (0.4 + human)
        if char in "()[]{}\"'":
            weight *= 1.0 + 0.14 * human
        if char.isdigit():
            weight *= 1.0 + 0.10 * human
        since_pause += 1
        if human > 0.25 and since_pause > random.randint(60, 150) and random.random() < 0.32 * human:
            weight *= 1.0 + random.uniform(1.1, 2.6) * human
            since_pause = 0
        weights.append(weight)
        prev = char

    target = n * mean
    total_w = sum(weights) or 1.0
    delays = [max(0.012, target * (weight / total_w)) for weight in weights]
    current = sum(delays)
    if current > 0:
        delays = [max(0.012, delay * (target / current)) for delay in delays]
    return delays


def _word_factors(text: str) -> list[float]:
    factors = [1.0] * len(text)
    i = 0
    while i < len(text):
        if not text[i].isalpha():
            i += 1
            continue
        j = i + 1
        while j < len(text) and (text[j].isalpha() or text[j] == "'"):
            j += 1
        word = text[i:j].lower()
        length = j - i
        factors[i] = 1.16
        rest = 1.0
        if word in COMMON_WORDS:
            rest = 0.68
        elif length <= 3:
            rest = 0.86
        elif length >= 10:
            rest = 1.14
        for k in range(i + 1, j):
            factors[k] = rest
        i = j
    return factors


def _travel(prev: str, char: str) -> float:
    if not prev:
        return 1.12
    a = KEY_POS.get(prev.lower())
    b = KEY_POS.get(char.lower())
    if a is None or b is None:
        return 1.0
    dist = math.hypot(a[0] - b[0], a[1] - b[1])
    factor = 0.88 + 0.09 * dist
    fa = FINGER.get(prev.lower())
    fb = FINGER.get(char.lower())
    if fa is not None and fa == fb and fa >= 0:
        factor *= 1.24
    elif fa is not None and fb is not None and fa >= 0 and fb >= 0 and (fa < 4) != (fb < 4):
        factor *= 0.80
    return max(0.55, min(1.85, factor))


def _notice(human: float, short: bool = False) -> None:
    """Wait until the target field has applied the last injected key."""
    if short:
        time.sleep(random.uniform(0.07, 0.12) * (0.75 + 0.25 * human))
        return
    time.sleep(random.uniform(0.12, 0.22) * (0.75 + 0.25 * human))


def _slip(keyboard: Keyboard, char: str, nxt: str, human: float) -> None:
    roll = random.random()
    if nxt.isalpha() and roll < 0.22:
        keyboard.write(nxt)
        tiny_settle()
        _notice(human, short=True)
        keyboard.write(char)
        tiny_settle()
        _notice(human)
        keyboard.backspace()
        tiny_settle()
        _notice(human, short=True)
        keyboard.backspace()
        tiny_settle()
        _notice(human, short=True)
        return
    if roll < 0.50:
        keyboard.write(char)
        tiny_settle()
        _notice(human)
        keyboard.backspace()
        tiny_settle()
        _notice(human, short=True)
        return
    wrong = _nearby(char)
    if not wrong:
        return
    keyboard.write(wrong)
    tiny_settle()
    _notice(human)
    keyboard.backspace()
    tiny_settle()
    _notice(human, short=True)


def _nearby(char: str) -> str:
    key = char.lower()
    options = NEIGHBORS.get(key, "")
    if not options:
        return ""
    pick = random.choice(options)
    return pick.upper() if char.isupper() else pick
