"""PyWorld is a Python wrapper for WORLD vocoder.

PyWorld wrappers WORLD, which is a free software for high-quality speech
analysis, manipulation and synthesis. It can estimate fundamental frequency (F0),
aperiodicity and spectral envelope and also generate the speech like input speech
with only estimated parameters.

For more information, see https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder
"""

from __future__ import division, print_function, absolute_import

from importlib.metadata import version

__version__ = version('pyworld')

from .pyworld import *

# Build-time info populated by setup.py. When absent (e.g., sdist before
# build, or an unusual install), fall back to "unknown" so consumers can
# still introspect without crashing.
try:
    from . import _build_info as _bi
    __fft_backend__ = _bi.FFT_BACKEND
    __avx512_enabled__ = _bi.AVX512_ENABLED
    __world_commit__ = _bi.WORLD_COMMIT
    __build_timestamp__ = _bi.BUILD_TIMESTAMP
except ImportError:
    __fft_backend__ = "unknown"
    __avx512_enabled__ = False
    __world_commit__ = "unknown"
    __build_timestamp__ = "unknown"


def build_info():
    """Return a one-line summary of how this pyworld extension was built."""
    return (
        "pyworld {version}  FFT={fft}  AVX-512={avx}  "
        "WORLD={commit}  built={ts}".format(
            version=__version__,
            fft=__fft_backend__,
            avx="on" if __avx512_enabled__ else "off",
            commit=__world_commit__,
            ts=__build_timestamp__,
        )
    )
