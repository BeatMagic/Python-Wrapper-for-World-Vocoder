from __future__ import absolute_import, print_function, with_statement

import os
import subprocess
import sys
import tarfile
from glob import glob
from os.path import join, exists, abspath, basename

import numpy
from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext as _build_ext


_VERSION = '0.3.4'

FFTW3_VERSION = '3.3.10'
FFTW3_URL = 'https://www.fftw.org/fftw-{}.tar.gz'.format(FFTW3_VERSION)

WORLD_SRC_TOP = join("lib", "World", "src")
WORLD_REPO = 'https://github.com/BeatMagic/World.git'
WORLD_BRANCH = 'perf/harvest-optimization'

# FFT backend: 'fftw3' (default) or 'ooura'
FFT_BACKEND = os.environ.get('PYWORLD_FFT_BACKEND', 'fftw3').lower()

# Placeholder extension — sources are resolved in build_ext after submodule init
ext_modules = [
    Extension(
        name="pyworld.pyworld",
        include_dirs=[WORLD_SRC_TOP, numpy.get_include()],
        sources=[join("pyworld", "pyworld.pyx")],
        language="c++")]


class build_ext(_build_ext):
    def _ensure_world_src(self):
        """Ensure World C++ sources are present (init submodule or clone)."""
        marker = join(WORLD_SRC_TOP, "harvest.cpp")
        if exists(marker):
            return
        # Try git submodule update first (works in a proper clone)
        if exists(".git"):
            print("Initializing World submodule...")
            subprocess.check_call(
                ["git", "submodule", "update", "--init", "--recursive"])
            if exists(marker):
                return
        # Fallback: direct clone (works for pip install git+https://...)
        print("Cloning World source from {}...".format(WORLD_REPO))
        world_dir = join("lib", "World")
        if exists(world_dir):
            import shutil
            shutil.rmtree(world_dir)
        subprocess.check_call([
            "git", "clone", "--depth", "1",
            "--branch", WORLD_BRANCH,
            WORLD_REPO, world_dir,
        ])

    def _collect_world_sources(self):
        """Collect World .cpp sources with the correct FFT backend."""
        sources = [f for f in glob(join(WORLD_SRC_TOP, "*.cpp"))
                   if basename(f) not in ('fft.cpp', 'fft_fftw3.cpp')]
        if FFT_BACKEND == 'fftw3':
            sources.append(join(WORLD_SRC_TOP, 'fft_fftw3.cpp'))
        else:
            sources.append(join(WORLD_SRC_TOP, 'fft.cpp'))
        return sources

    def _build_fftw3(self):
        """Download and build FFTW3 from source as a static library."""
        build_temp = abspath(self.build_temp)
        fftw3_src = join(build_temp, 'fftw-{}'.format(FFTW3_VERSION))
        fftw3_prefix = join(build_temp, 'fftw3_install')

        # Skip if already built
        lib_path = join(fftw3_prefix, 'lib', 'libfftw3.a')
        if exists(lib_path):
            return fftw3_prefix

        os.makedirs(build_temp, exist_ok=True)

        # Download
        tarball = join(build_temp, 'fftw-{}.tar.gz'.format(FFTW3_VERSION))
        if not exists(tarball):
            print('Downloading FFTW3 {}...'.format(FFTW3_VERSION))
            try:
                from urllib.request import urlretrieve
            except ImportError:
                from urllib import urlretrieve
            urlretrieve(FFTW3_URL, tarball)

        # Extract
        if not exists(fftw3_src):
            print('Extracting FFTW3...')
            with tarfile.open(tarball) as tar:
                tar.extractall(build_temp)

        # Configure and build
        print('Building FFTW3 (this may take a few minutes)...')
        os.makedirs(fftw3_prefix, exist_ok=True)

        subprocess.check_call([
            join(fftw3_src, 'configure'),
            '--prefix={}'.format(fftw3_prefix),
            '--enable-static',
            '--disable-shared',
            '--with-pic',
            '--disable-fortran',
        ], cwd=fftw3_src)
        subprocess.check_call(
            ['make', '-j{}'.format(os.cpu_count() or 4)], cwd=fftw3_src)
        subprocess.check_call(['make', 'install'], cwd=fftw3_src)

        return fftw3_prefix

    def build_extensions(self):
        print('FFT backend: {}'.format(FFT_BACKEND))

        # Step 1: ensure World C++ sources exist
        self._ensure_world_src()
        world_sources = self._collect_world_sources()

        # Step 2: inject World sources into the extension
        for ext in self.extensions:
            ext.sources.extend(world_sources)

        # Step 3: build FFTW3 from source if needed
        if FFT_BACKEND == 'fftw3':
            fftw3_prefix = self._build_fftw3()
            fftw3_include = join(fftw3_prefix, 'include')
            fftw3_lib = join(fftw3_prefix, 'lib')
            for ext in self.extensions:
                ext.include_dirs.append(fftw3_include)
                ext.library_dirs = [fftw3_lib]
                ext.libraries = ['fftw3']

        # Step 4: optimization flags
        for ext in self.extensions:
            if sys.platform != 'win32':
                ext.extra_compile_args = ['-O3', '-ffast-math']

        _build_ext.build_extensions(self)


kwargs = {"encoding": "utf-8"} if int(sys.version[0]) > 2 else {}
setup(
    name="pyworld",
    description="PyWorld: a Python wrapper for WORLD vocoder",
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
    url="https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder",
    keywords=['vocoder'],
    classifiers=[],
)
