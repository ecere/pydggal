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
from os import path

dir = os.path.dirname(__file__)
if dir == '':
   rwd = os.path.abspath('.')
else:
   rwd = os.path.abspath(dir)
with open(os.path.join(rwd, 'README.md'), encoding='u8') as f:
   long_description = f.read()

pkg_version       = '0.0.1'

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
      binsOption = 'EC_BINS=' + os.path.join(ecdev_location, 'bin', '')
      ldFlags = 'LDFLAGS=-L' + os.path.join(ecdev_location, dll_dir, '')
      env = os.environ.copy()
      set_library_path(env, os.path.join(ecdev_location, 'lib'))
      if not os.path.exists(artifacts_dir):
         subprocess.check_call([make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y', 'ENABLE_PYTHON_RPATHS=y', 'DISABLED_STATIC_BUILDS=y', sdkOption, binsOption, ldFlags], env=env, cwd=dggal_dir)
         #subprocess.check_call([make_cmd, f'-j{cpu_count}', 'SKIP_SONAME=y', 'ENABLE_PYTHON_RPATHS=y',  'DISABLED_STATIC_BUILDS=y', sdkOption, binsOption, ldFlags], env=env, cwd=dggal_c_dir)
         prepare_package_dir([
            (os.path.join(lib_dir, dll_prefix + 'dggal' + dll_ext), os.path.join(dll_dir, dll_prefix + 'dggal' + dll_ext)),
            #(os.path.join(lib_dir, dll_prefix + 'dggal_c' + dll_ext), os.path.join(dll_dir, dll_prefix + 'dggal_c' + dll_ext)),
            (os.path.join(dggal_py_dir, 'dggal.py'), 'dggal.py'),
            (os.path.join(dggal_py_dir, '__init__.py'), '__init__.py'),
            (os.path.join(dggal_dir, 'obj', 'release.' + platform_str, 'dgg' + exe_ext), os.path.join('bin', 'dgg' + exe_ext)),
            (os.path.join(os.path.dirname(__file__), 'dgg_wrapper.py'), os.path.join('bin', 'dgg_wrapper.py')),
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
   cffi_modules=[]
else:
   packages=['dggal', 'dggal.lib', 'dggal.bin']
   package_dir={'dggal': artifacts_dir, 'dggal.bin': os.path.join(artifacts_dir, 'bin')}
   package_data={'dggal': [ 'dggal.py' ], 'dggal.bin': ['dgg' + exe_ext, 'dgg_wrapper.py']}
   if platform_str != 'win32':
      package_dir['dggal.lib'] =  os.path.join(artifacts_dir, 'lib')
      package_data['dggal.lib'] = lib_files
   else:
      package_data['dggal.bin'].extent(lib_files)

   cmdclass={'build': build_with_make, 'egg_info': egg_info_with_build }
   cffi_modules=[os.path.join('dggal', 'bindings', 'py', 'build_dggal.py') + ':ffi_dggal']

setup(
    name='dggal',
    version='0.0.1',
    cffi_modules=cffi_modules,
    setup_requires=['ecdev', 'ecrt', 'cffi >= 1.0.0'],
    install_requires=['ecrt', 'cffi >= 1.0.0'],
    packages=packages,
    package_dir=package_dir,
    package_data=package_data,
    include_package_data=True,
    ext_modules=[],
    cmdclass=cmdclass,
    entry_points={ 'console_scripts': [ 'dgg=dggal.bin.dgg_wrapper:main' ] }
)
