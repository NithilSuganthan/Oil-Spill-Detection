"""Probability mask -> binary mask -> morphological cleanup.

Pure NumPy so the pipeline has no heavy CV dependency.
"""

from __future__ import annotations

import numpy as np


def threshold_mask(probability: np.ndarray, threshold: float) -> np.ndarray:
    """prob >= threshold -> True (candidate slick pixels)."""
    return probability >= threshold


def _shift_or(mask: np.ndarray) -> np.ndarray:
    """Binary dilation with a 3x3 structuring element."""
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def _shift_and(mask: np.ndarray) -> np.ndarray:
    """Binary erosion with a 3x3 structuring element."""
    out = mask.copy()
    out[1:, :] &= mask[:-1, :]
    out[:-1, :] &= mask[1:, :]
    out[:, 1:] &= mask[:, :-1]
    out[:, :-1] &= mask[:, 1:]
    return out


def _dilate(mask: np.ndarray, n: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(n):
        out = _shift_or(out)
    return out


def _erode(mask: np.ndarray, n: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(n):
        out = _shift_and(out)
    return out


def morphological_cleanup(
    mask: np.ndarray, close_iterations: int = 2, open_iterations: int = 2
) -> np.ndarray:
    """Closing then opening with a 3x3 cross structuring element.

    closing = dilate(n) -> erode(n)   fills pinholes / gaps
    opening = erode(n)  -> dilate(n)  removes isolated specks
    """
    out = _dilate(mask, close_iterations)
    out = _erode(out, close_iterations)
    out = _erode(out, open_iterations)
    out = _dilate(out, open_iterations)
    return out
