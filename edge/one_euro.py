"""Independent implementation of the 1 Euro filter, CHI 2012, Appendix A.

Casiez, Roussel, Vogel. DOI: 10.1145/2207676.2208639
https://gery.casiez.net/publications/CHI2012-casiez.pdf
The derivative uses the preceding filtered value as in Appendix A, Algorithm 1.
Gap resets and invalid/repeated timestamp handling are project-specific guards.
"""

import math


class OneEuroFilter:
    def __init__(self, min_cutoff=1.0, beta=0.5, d_cutoff=1.0, max_gap=2.0):
        values = (min_cutoff, beta, d_cutoff, max_gap)
        if (not all(math.isfinite(v) for v in values) or min_cutoff <= 0
                or beta < 0 or d_cutoff <= 0 or max_gap <= 0):
            raise ValueError("Filter cutoffs/gap must be finite positive; beta must be nonnegative")
        self.min_cutoff, self.beta = min_cutoff, beta
        self.d_cutoff, self.max_gap = d_cutoff, max_gap
        self.reset()

    @staticmethod
    def alpha(cutoff, dt):
        return 1.0 / (1.0 + 1.0 / (2.0 * math.pi * cutoff * dt))

    def reset(self, value=None, timestamp=None):
        if (value is None) != (timestamp is None):
            raise ValueError("Seed value and timestamp must be provided together")
        if value is not None and not (math.isfinite(value) and math.isfinite(timestamp)):
            raise ValueError("Seed must be finite")
        self.value, self.timestamp = value, timestamp
        self.derivative = 0.0

    def __call__(self, value, timestamp):
        if not (math.isfinite(value) and math.isfinite(timestamp)):
            raise ValueError("Sample and timestamp must be finite")
        if self.timestamp is None:
            self.reset(value, timestamp)
            return value
        dt = timestamp - self.timestamp
        if dt <= 0:
            return self.value
        if dt > self.max_gap:
            self.reset(value, timestamp)
            return value
        derivative = (value - self.value) / dt
        ad = self.alpha(self.d_cutoff, dt)
        filtered_derivative = ad * derivative + (1 - ad) * self.derivative
        cutoff = self.min_cutoff + self.beta * abs(filtered_derivative)
        a = self.alpha(cutoff, dt)
        self.value = a * value + (1 - a) * self.value
        self.timestamp, self.derivative = timestamp, filtered_derivative
        return self.value
