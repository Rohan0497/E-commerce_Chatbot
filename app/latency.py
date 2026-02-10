# app/latency.py
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

import numpy as np


@dataclass
class LatencyStats:
    p50_ms: float
    p95_ms: float
    n: int


class LatencyRecorder:
    """
    Keeps a rolling window of request latencies in memory.
    """
    def __init__(self, maxlen: int = 2000):
        self._values_ms: Deque[float] = deque(maxlen=maxlen)

    def add(self, ms: float) -> None:
        self._values_ms.append(float(ms))

    def stats(self) -> Optional[LatencyStats]:
        if not self._values_ms:
            return None
        arr = np.array(self._values_ms, dtype=float)
        return LatencyStats(
            p50_ms=float(np.percentile(arr, 50)),
            p95_ms=float(np.percentile(arr, 95)),
            n=int(arr.size),
        )
