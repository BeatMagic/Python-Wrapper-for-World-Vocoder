from __future__ import absolute_import, print_function, with_statement

import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from glob import glob
from os.path import join, exists, abspath, basename, normpath

import numpy
from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext as _build_ext


_VERSION = '0.4.0'

# Upstream FFTW 3.3.10 (fallback; no AVX-512)
FFTW3_VERSION = '3.3.10'
FFTW3_URL = 'https://www.fftw.org/fftw-{}.tar.gz'.format(FFTW3_VERSION)

# AOCL-FFTW: AMD's fork of FFTW 3.3.10 with AVX-512 codelets + AMD-opt.
AOCL_FFTW_REPO = 'https://github.com/amd/amd-fftw.git'
AOCL_FFTW_TAG = '5.2'

WORLD_REPO = 'https://github.com/BeatMagic/World.git'
WORLD_BRANCH = 'perf/harvest-optimization'
WORLD_LIB_TOP = join("lib", "World")
WORLD_SRC_TOP = join(WORLD_LIB_TOP, "src")
WORLD_SIMD_SRC = join(WORLD_SRC_TOP, "simd")

# Backend selection:
#   auto (default)  Linux x86_64 + AMD CPU + autotools present -> aocl, else fftw3
#   aocl            force AOCL-FFTW (fails loudly if tools missing)
#   fftw3           force upstream FFTW 3.3.10
#   ooura           use bundled Ooura FFT (no external deps, slowest)
FFT_BACKEND_REQ = os.environ.get('PYWORLD_FFT_BACKEND', 'auto').lower()

# AVX-512 enable: auto (default) detects compiler support; '0'/'false' to disable.
AVX512_ENV = os.environ.get('PYWORLD_AVX512', 'auto').lower()

AVX512_FLAGS = [
    '-mavx512f', '-mavx512dq', '-mavx512bw', '-mavx512vl', '-mfma', '-mbmi2',
]


def _is_linux_x86_64():
    return sys.platform.startswith('linux') and platform.machine().lower() in (
        'x86_64', 'amd64')


def _cpuinfo_fields():
    """Return (vendor_id, cpu_family_int) from /proc/cpuinfo, or (None, None)."""
    vendor = None
    family = None
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                parts = line.split(':', 1)
                if len(parts) != 2:
                    continue
                key = parts[0].strip()
                val = parts[1].strip()
                if key == 'vendor_id' and vendor is None:
                    vendor = val
                elif key == 'cpu family' and family is None:
                    try:
                        family = int(val)
                    except ValueError:
                        pass
                if vendor is not None and family is not None:
                    break
    except (OSError, IOError):
        pass
    return vendor, family


def _is_amd_cpu():
    vendor, _ = _cpuinfo_fields()
    return vendor == 'AuthenticAMD'


def _is_amd_zen5():
    # AMD Zen5 (Ryzen 9000 / EPYC Turin) reports cpu family 26 (0x1A).
    vendor, family = _cpuinfo_fields()
    return vendor == 'AuthenticAMD' and family == 26


_AOCL_REQUIRED_TOOLS = ('git', 'autoconf', 'automake', 'libtool', 'ocaml',
                        'make', 'cc', 'makeinfo')


def _have_tool(name):
    return shutil.which(name) is not None


def _have_aocl_build_tools():
    return all(_have_tool(t) for t in _AOCL_REQUIRED_TOOLS)


def _require_aocl_build_tools(reason):
    missing = [t for t in _AOCL_REQUIRED_TOOLS if not _have_tool(t)]
    if missing:
        raise SystemExit(
            '[pyworld] ERROR: {reason} but required tools are missing: {miss}\n'
            '  Install and re-run pip install. On Debian/Ubuntu:\n'
            '    sudo apt-get install -y build-essential git autoconf automake '
            'libtool-bin ocaml texinfo\n'
            '  To opt out and use upstream FFTW instead, set '
            'PYWORLD_FFT_BACKEND=fftw3.'.format(
                reason=reason, miss=', '.join(missing)))


def _detect_avx512_compiler_support():
    if AVX512_ENV in ('0', 'false', 'off', 'no'):
        return False
    if sys.platform == 'win32':
        # This fork's AVX-512 path targets GCC/Clang on Linux; MSVC support
        # exists in the WORLD CMake build but not wired into setup.py.
        return False
    compiler = os.environ.get('CC', 'cc')
    if not _have_tool(compiler):
        return False
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
        f.write('#include <immintrin.h>\n'
                'int main(void){\n'
                '  __m512d a=_mm512_set1_pd(1.0),b=_mm512_set1_pd(2.0);\n'
                '  __m512d c=_mm512_add_pd(a,b); (void)c; return 0;\n'
                '}\n')
        src_path = f.name
    obj_path = src_path + '.o'
    try:
        result = subprocess.run(
            [compiler] + AVX512_FLAGS + ['-c', '-o', obj_path, src_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        for p in (src_path, obj_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def _resolve_fft_backend():
    # Explicit override takes precedence, but still validates deps.
    if FFT_BACKEND_REQ in ('aocl', 'fftw3', 'ooura'):
        if FFT_BACKEND_REQ == 'aocl':
            if not _is_linux_x86_64():
                raise SystemExit(
                    '[pyworld] PYWORLD_FFT_BACKEND=aocl requested but host is '
                    'not Linux x86_64; AOCL-FFTW is Linux-only in this '
                    'wrapper. Set PYWORLD_FFT_BACKEND=fftw3 or leave unset.')
            _require_aocl_build_tools('PYWORLD_FFT_BACKEND=aocl')
        return FFT_BACKEND_REQ

    # auto mode
    # Zen5 (AMD family 26) is the primary target of this fork; AOCL's AVX-512
    # codelets give the biggest win there. Force AOCL and fail loudly if the
    # build environment is incomplete -- silently falling back to upstream
    # FFTW would mask a ~15% speedup loss.
    if _is_linux_x86_64() and _is_amd_zen5():
        print('[pyworld] Detected AMD Zen5 (cpu family 26). '
              'Forcing AOCL-FFTW path (no silent fallback).')
        _require_aocl_build_tools('Zen5 auto-selected AOCL-FFTW')
        return 'aocl'

    # Other AMD (Zen1..Zen4) on Linux: use AOCL if tools are present, else
    # fall back silently to upstream FFTW. Missing AVX-512 codelets are less
    # of a regression on pre-Zen5 silicon (Zen4 double-pumps AVX-512 anyway).
    if _is_linux_x86_64() and _is_amd_cpu() and _have_aocl_build_tools():
        return 'aocl'
    return 'fftw3'


# ---------------------------------------------------------------------------
# Extension placeholder; sources filled in during build_extensions.
# ---------------------------------------------------------------------------

ext_modules = [
    Extension(
        name="pyworld.pyworld",
        include_dirs=[WORLD_SRC_TOP, numpy.get_include()],
        sources=[join("pyworld", "pyworld.pyx")],
        language="c++",
    )
]


class build_ext(_build_ext):
    def _ensure_world_src(self):
        """Ensure World C++ sources are present (init submodule or clone)."""
        marker = join(WORLD_SRC_TOP, "harvest.cpp")
        if exists(marker):
            return
        if exists(".git"):
            print("[pyworld] Initializing World submodule...")
            subprocess.check_call(
                ["git", "submodule", "update", "--init", "--recursive"])
            if exists(marker):
                return
        # Fallback: direct clone for pip install git+https://...
        print("[pyworld] Cloning World source from {}...".format(WORLD_REPO))
        if exists(WORLD_LIB_TOP):
            shutil.rmtree(WORLD_LIB_TOP)
        subprocess.check_call([
            "git", "clone", "--depth", "1",
            "--branch", WORLD_BRANCH,
            WORLD_REPO, WORLD_LIB_TOP,
        ])

    def _collect_world_sources(self, backend):
        """World .cpp sources for the given FFT backend + SIMD dispatcher."""
        top_sources = [f for f in sorted(glob(join(WORLD_SRC_TOP, "*.cpp")))
                       if basename(f) not in ('fft.cpp', 'fft_fftw3.cpp')]
        if backend == 'ooura':
            top_sources.append(join(WORLD_SRC_TOP, 'fft.cpp'))
        else:
            top_sources.append(join(WORLD_SRC_TOP, 'fft_fftw3.cpp'))
        simd_sources = sorted(glob(join(WORLD_SIMD_SRC, "*.cpp")))
        return top_sources + simd_sources

    def _build_upstream_fftw3(self):
        """Download and build upstream FFTW 3.3.10 as a static lib."""
        build_temp = abspath(self.build_temp)
        fftw3_src = join(build_temp, 'fftw-{}'.format(FFTW3_VERSION))
        prefix = join(build_temp, 'fftw3_install')
        lib = join(prefix, 'lib', 'libfftw3.a')
        if exists(lib):
            return prefix
        os.makedirs(build_temp, exist_ok=True)
        tarball = join(build_temp, 'fftw-{}.tar.gz'.format(FFTW3_VERSION))
        if not exists(tarball):
            print('[pyworld] Downloading upstream FFTW {}...'.format(FFTW3_VERSION))
            try:
                from urllib.request import urlretrieve
            except ImportError:
                from urllib import urlretrieve
            urlretrieve(FFTW3_URL, tarball)
        if not exists(fftw3_src):
            print('[pyworld] Extracting FFTW...')
            with tarfile.open(tarball) as tar:
                tar.extractall(build_temp)
        print('[pyworld] Building upstream FFTW (this may take a few minutes)...')
        os.makedirs(prefix, exist_ok=True)
        cfg = [
            join(fftw3_src, 'configure'),
            '--prefix={}'.format(prefix),
            '--enable-static', '--disable-shared',
            '--with-pic',
            '--disable-fortran',
        ]
        if _is_linux_x86_64():
            cfg += ['--enable-sse2', '--enable-avx', '--enable-avx2', '--enable-fma']
        subprocess.check_call(cfg, cwd=fftw3_src)
        subprocess.check_call(
            ['make', '-j{}'.format(os.cpu_count() or 4)], cwd=fftw3_src)
        subprocess.check_call(['make', 'install'], cwd=fftw3_src)
        return prefix

    def _build_aocl_fftw(self):
        """Clone and build AOCL-FFTW 5.2 with AVX-512 + AMD-opt codelets."""
        build_temp = abspath(self.build_temp)
        src = join(build_temp, 'amd-fftw')
        prefix = join(build_temp, 'aocl_fftw_install')
        lib = join(prefix, 'lib', 'libfftw3.a')
        if exists(lib):
            return prefix
        os.makedirs(build_temp, exist_ok=True)
        if not exists(src):
            print('[pyworld] Cloning AOCL-FFTW {}...'.format(AOCL_FFTW_TAG))
            subprocess.check_call([
                'git', 'clone', '--depth', '1',
                '--branch', AOCL_FFTW_TAG,
                AOCL_FFTW_REPO, src,
            ])
        print('[pyworld] Bootstrapping AOCL-FFTW...')
        subprocess.check_call(['bash', './bootstrap.sh'], cwd=src)
        print('[pyworld] Building AOCL-FFTW (this may take several minutes)...')
        os.makedirs(prefix, exist_ok=True)
        env = os.environ.copy()
        env.setdefault('CFLAGS', '-O3 -fPIC')
        cfg = [
            join(src, 'configure'),
            '--prefix={}'.format(prefix),
            '--enable-static', '--disable-shared',
            '--with-pic',
            '--disable-fortran',
            '--enable-sse2', '--enable-avx', '--enable-avx2',
            '--enable-avx512', '--enable-amd-opt',
            '--enable-dynamic-dispatcher',
        ]
        subprocess.check_call(cfg, cwd=src, env=env)
        subprocess.check_call(
            ['make', '-j{}'.format(os.cpu_count() or 4)], cwd=src, env=env)
        subprocess.check_call(['make', 'install'], cwd=src, env=env)
        return prefix

    def build_extensions(self):
        # Step 1: ensure World C++ sources exist
        self._ensure_world_src()

        # Step 2: resolve backend
        backend = _resolve_fft_backend()
        print('[pyworld] FFT backend: {}'.format(backend))

        # Step 3: collect sources (World core + fft_backend + simd/*)
        world_sources = self._collect_world_sources(backend)
        for ext in self.extensions:
            ext.sources.extend(world_sources)

        # Step 4: build chosen FFT backend (if not ooura)
        fft_prefix = None
        if backend == 'aocl':
            fft_prefix = self._build_aocl_fftw()
        elif backend == 'fftw3':
            fft_prefix = self._build_upstream_fftw3()

        if fft_prefix is not None:
            for ext in self.extensions:
                ext.include_dirs.append(join(fft_prefix, 'include'))
                ext.library_dirs = [join(fft_prefix, 'lib')]
                ext.libraries = ['fftw3']

        # Step 5: optimization + AVX-512 flags.
        # Baseline flags apply to every source. AVX-512 flags apply ONLY to
        # simd_kernels_avx512.cpp so that the compiled .so still loads on
        # non-AVX-512 CPUs; the runtime dispatcher in WORLD picks scalar there.
        avx512_ok = _detect_avx512_compiler_support()
        base_args = []
        base_defs = []
        if sys.platform != 'win32':
            base_args = ['-O3', '-ffast-math']
        if avx512_ok:
            base_defs.append(('WORLD_HAS_AVX512', '1'))
        for ext in self.extensions:
            ext.extra_compile_args = list(base_args)
            ext.define_macros = list(ext.define_macros or []) + base_defs
        if avx512_ok:
            print('[pyworld] AVX-512 kernels enabled (per-file flags on '
                  'simd_kernels_avx512.cpp).')
        else:
            print('[pyworld] AVX-512 kernels compiled as stub (scalar fallback '
                  'only).')

        # Patch the compiler to inject per-file AVX-512 flags on the one AVX-512
        # translation unit. Reverted after build.
        avx512_tu = normpath(join(WORLD_SIMD_SRC, 'simd_kernels_avx512.cpp'))
        compiler = self.compiler
        orig_compile = getattr(compiler, '_compile', None)
        if avx512_ok and orig_compile is not None:
            def patched_compile(obj, src, ext_, cc_args, extra_postargs, pp_opts):
                if normpath(src) == avx512_tu:
                    extra_postargs = list(extra_postargs) + AVX512_FLAGS
                return orig_compile(obj, src, ext_, cc_args, extra_postargs, pp_opts)
            compiler._compile = patched_compile
        try:
            _build_ext.build_extensions(self)
        finally:
            if avx512_ok and orig_compile is not None:
                compiler._compile = orig_compile


kwargs = {"encoding": "utf-8"} if int(sys.version[0]) > 2 else {}
setup(
    name="pyworld",
    description="PyWorld: a Python wrapper for WORLD vocoder "
                "(AVX-512 + AOCL-FFTW fork)",
    long_description=open("README.md", "r", **kwargs).read(),
    long_description_content_type="text/markdown",
    ext_modules=ext_modules,
    cmdclass={'build_ext': build_ext},
    version=_VERSION,
    packages=find_packages(),
    install_requires=['numpy'],
    extras_require={
        'test': ['nose'],
        'sdist': ['numpy', 'cython>=0.24'],
    },
    author="Pyworld Contributors",
    author_email="jeremycchsu@gmail.com",
    url="https://github.com/BeatMagic/Python-Wrapper-for-World-Vocoder",
    keywords=['vocoder', 'avx512', 'aocl-fftw'],
    classifiers=[],
)
