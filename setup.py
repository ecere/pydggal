from setuptools import setup, Extension
import multiprocessing
from setuptools.command.build import build
from setuptools.command.egg_info import egg_info
import subprocess
import os
import sys
import shutil
import sysconfig
import pkg_resources
import platform
import distutils.ccompiler
from distutils.command.build_ext import build_ext
#from wheel.bdist_wheel import bdist_wheel
from os import path

pkg_version = '0.0.3'

env = os.environ.copy()

cc_override = None

# print("sys.platform is: ", sys.platform)

if sys.platform.startswith('win'):

   # NOTE: PyPy builds are failing due to a .def file containing a PyInit_ symbol which is specific to CPython
   # See generated build/temp.win-amd64-pypy38/Release/build/temp.win-amd64-pypy38/release/_pyecrt.pypy38-pp73-win_amd64.def
   # and https://github.com/python-cffi/cffi/issues/170

   # This approach works with Python 3.8
   def get_mingw(plat=None):
       return 'mingw32'

   distutils.ccompiler.get_default_compiler = get_mingw

   # This approach works with Python 3.9+
   class CustomBuildExt(build_ext):
      def initialize_options(self):
         super().initialize_options()
         self.compiler = 'mingw32'

   def get_gcc_target():
       try:
           output = subprocess.check_output(['gcc', '-dumpmachine'], universal_newlines=True)
           return output.strip()
       except Exception:
           return None

   def check_gcc_multilib():
       try:
           output = subprocess.check_output(['gcc', '-v'], stderr=subprocess.STDOUT, universal_newlines=True)
           return '--enable-multilib' in output
       except Exception:
           return False

   def is_gcc_good_for(archBits):
       target = get_gcc_target()
       if target is None:
           return True
       supports_multilib = check_gcc_multilib()

       if target.startswith('x86_64'):
           return archBits == 64
       elif target.startswith('i686') or target.startswith('i386'):
           return archBits == 32
       else:
           return True # Unknown

   def check_i686_w64_available():
       try:
           result = subprocess.run(
               ['i686-w64-mingw32-gcc', '--version'],
               stdout=subprocess.PIPE,
               stderr=subprocess.PIPE,
               check=True,
               universal_newlines=True
           )
           return True
       except (subprocess.CalledProcessError, FileNotFoundError):
           return False

   if platform.architecture()[0] == '64bit':
      # Ensure ProgramFiles(x86) is set
      if 'ProgramFiles(x86)' not in env:
         env['ProgramFiles(x86)'] = r"C:\Program Files (x86)"
   else:
      if 'ProgramFiles(x86)' in env:
         del os.environ['ProgramFiles(x86)']
      if is_gcc_good_for(32) == False:
         if check_i686_w64_available():
            cc_override = ['GCC_PREFIX=i686-w64-mingw32-']

dir = os.path.dirname(__file__)
if dir == '':
   rwd = os.path.abspath('.')
else:
   rwd = os.path.abspath(dir)
with open(os.path.join(rwd, 'README.md'), encoding='u8') as f:
   long_description = f.read()

cpu_count = multiprocessing.cpu_count()
dggal_dir = os.path.join(os.path.dirname(__file__), 'dggal')
dggal_c_dir = os.path.join(os.path.dirname(__file__), 'dggal', 'bindings', 'c')
dggal_py_dir = os.path.join(os.path.dirname(__file__), 'dggal', 'bindings', 'py')
platform_str = 'win32' if sys.platform.startswith('win') else ('apple' if sys.platform.startswith('darwin') else 'linux')
dll_prefix = '' if platform_str == 'win32' else 'lib'
dll_dir = 'bin' if platform_str == 'win32' else 'lib'
dll_ext = '.dll' if platform_str == 'win32' else '.dylib' if platform_str == 'apple' else '.so'
exe_ext = '.exe' if platform_str == 'win32' else ''
pymodule = '_pydggal' + sysconfig.get_config_var('EXT_SUFFIX')
artifacts_dir = os.path.join('artifacts', platform_str)
lib_dir = os.path.join(dggal_dir, 'obj', platform_str, dll_dir)

make_cmd = 'mingw32-make' if platform_str == 'win32' else 'make'

def set_library_path(env, lib_path):
    platform_str = sys.platform
    if platform_str == 'darwin':
        current = env.get('DYLD_LIBRARY_PATH', '')
        env['DYLD_LIBRARY_PATH'] = lib_path + (':' + current if current else '')
    elif platform_str.startswith('win'):
        current = env.get('PATH', '')
        env['PATH'] = lib_path + (';' + current if current else '')
    else: # if platform_str.startswith('linux'):
        current = env.get('LD_LIBRARY_PATH', '')
        env['LD_LIBRARY_PATH'] = lib_path + (':' + current if current else '')
        #print("NOW: ", env['LD_LIBRARY_PATH'])

def prepare_package_dir(src_files, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    for src, rel_dest in src_files:
        dest_path = os.path.join(dest_dir, rel_dest)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy(src, dest_path)

def build_package():
   try:
      ecdev_location = os.path.join(pkg_resources.get_distribution("ecdev").location, 'ecdev')
      sdkOption = 'EC_SDK_SRC=' + ecdev_location

      binsPath = os.path.join(ecdev_location, 'bin', '')
      libsPath = os.path.join(ecdev_location, dll_dir, '')
      if platform_str == 'win32':
         binsPath = binsPath.replace(os.sep, '/') # crossplatform.mk expects POSIX paths
         libsPath = libsPath.replace(os.sep, '/')
      binsOption = 'EC_BINS=' + binsPath
      ldFlags = 'LDFLAGS=-L' + libsPath
      set_library_path(env, os.path.join(ecdev_location, 'lib'))
      if not os.path.exists(artifacts_dir):
         make_and_args = [make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y', 'ENABLE_PYTHON_RPATHS=y', 'DISABLED_STATIC_BUILDS=y', sdkOption, binsOption, ldFlags]
         if cc_override is not None:
            make_and_args.extend(cc_override)
         subprocess.check_call(make_and_args, env=env, cwd=dggal_dir)
         #subprocess.check_call([make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y', 'ENABLE_PYTHON_RPATHS=y', 'DISABLED_STATIC_BUILDS=y', sdkOption, binsOption, ldFlags], env=env, cwd=dggal_c_dir)
         prepare_package_dir([
            (os.path.join(lib_dir, dll_prefix + 'dggal' + dll_ext), os.path.join(dll_dir, dll_prefix + 'dggal' + dll_ext)),
            #(os.path.join(lib_dir, dll_prefix + 'dggal_c' + dll_ext), os.path.join(dll_dir, dll_prefix + 'dggal_c' + dll_ext)),
            #(os.path.join(dggal_dir, 'obj', 'static.' + platform_str, 'libdggalStatic.a'), os.path.join('lib', 'libdggalStatic.a')),
            (os.path.join(dggal_py_dir, 'dggal.py'), 'dggal.py'),
            (os.path.join(dggal_py_dir, '__init__.py'), '__init__.py'),
            (os.path.join(dggal_dir, 'obj', 'release.' + platform_str, 'dgg' + exe_ext), os.path.join('bin', 'dgg' + exe_ext)),
            (os.path.join(os.path.dirname(__file__), 'dgg_wrapper.py'), os.path.join('bin', 'dgg_wrapper.py')),
            (os.path.join(dggal_dir, 'bindings_examples', 'py', 'geom.py'), os.path.join('examples', 'geom.py')),
            (os.path.join(dggal_dir, 'bindings_examples', 'py', 'info.py'), os.path.join('examples', 'info.py')),
            (os.path.join(dggal_dir, 'bindings_examples', 'py', 'togeo.py'), os.path.join('examples', 'togeo.py')),
            (os.path.join(dggal_dir, 'bindings_examples', 'py', 'togeo_json.py'), os.path.join('examples', 'togeo_json.py')),
            (os.path.join(dggal_dir, 'bindings_examples', 'py', 'togeo_text.py'), os.path.join('examples', 'togeo_text.py')),
         ], artifacts_dir)
   except subprocess.CalledProcessError as e:
      print(f"Error during make: {e}")
      sys.exit(1)

class build_with_make(build):
    def initialize_options(self):
        super().initialize_options()
    def run(self):
        build_package()
        super().run()

class egg_info_with_build(egg_info):
    def initialize_options(self):
        super().initialize_options()
    def run(self):
        build_package()
        super().run()

lib_files = [
   dll_prefix + 'dggal' + dll_ext,
   #dll_prefix + 'dggal_c' + dll_ext,
]

commands = set(sys.argv)

if 'sdist' in commands:
   packages=['dggal']
   package_dir = { 'dggal': 'dggal' }
   package_data = {'dggal': [] }
   cmdclass = {}
   cffi_modules = []
else:
   packages=['dggal', 'dggal.bin', 'dggal.examples']
   package_dir={
      'dggal': artifacts_dir,
      'dggal.bin': os.path.join(artifacts_dir, 'bin'),
      'dggal.examples': os.path.join(artifacts_dir, 'examples'),
   }
   package_data={
      'dggal': [ 'dggal.py' ],
      'dggal.bin': ['dgg' + exe_ext, 'dgg_wrapper.py'],
      #'dggal.lib': ['libdggalStatic.a'],
      'dggal.examples': ['geom.py', 'info.py', 'list.py', 'togeo.py', 'togeo_json.py', 'togeo_text.py'],
   }
   if platform_str == 'win32':
      package_data['dggal.bin'].append(dll_prefix + 'dggal' + dll_ext)
   else:
      packages.append('dggal.lib')
      package_dir['dggal.lib'] = os.path.join(artifacts_dir, 'lib')
      package_data['dggal.lib'] = [ dll_prefix + 'dggal' + dll_ext ]

   cmdclass={'build': build_with_make, 'egg_info': egg_info_with_build }
   if sys.platform.startswith('win'):
      cmdclass['build_ext'] = CustomBuildExt

   cffi_modules=[os.path.join('dggal', 'bindings', 'py', 'build_dggal.py') + ':ffi_dggal']

setup(
    name='dggal',
    version=pkg_version,
    cffi_modules=cffi_modules,
    setup_requires=['setuptools', 'ecdev', 'cffi >= 1.0.0'],
    install_requires=['ecrt >= 0.0.3', 'cffi >= 1.0.0'],
    packages=packages,
    package_dir=package_dir,
    package_data=package_data,
    include_package_data=True,
    ext_modules=[],
    cmdclass=cmdclass,
    entry_points={ 'console_scripts': [ 'dgg=dggal.bin.dgg_wrapper:main' ] },
    description='The Discrete Global Grid Abstraction Library (DGGAL)',
    url='https://dggal.org',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Jérôme Jacovella-St-Louis, Ecere Corporation',
    author_email='jerome@ecere.com',
    license='BSD-3-Clause',
    keywords='dggs hexagonal-grid global-grid ogc ogc-api gnosis dggrs isea ivea rtea isea3h isea9r ivea3h ivea9r slice-and-dice polyhedral-globe icosahedral rhealpix',
    classifiers=[
         'Development Status :: 4 - Beta',
         'Environment :: Console',
         'Intended Audience :: Developers',
         'Intended Audience :: Science/Research',
         'Operating System :: Microsoft :: Windows',
         'Operating System :: POSIX :: Linux',
         'Programming Language :: Other',
         'Programming Language :: Python :: 3',
         'Topic :: Software Development :: Libraries',
         'Topic :: Scientific/Engineering :: GIS',
         'Topic :: Scientific/Engineering :: Astronomy',
         'Topic :: Scientific/Engineering :: Atmospheric Science',
         'Topic :: Scientific/Engineering :: Hydrology',
         'Topic :: Scientific/Engineering :: Image Processing',
         'Topic :: Scientific/Engineering :: Information Analysis',
         'Topic :: Scientific/Engineering :: Oceanography',
         'Topic :: Scientific/Engineering :: Visualization',
    ],
)
