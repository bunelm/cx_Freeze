"""
Distutils script for cx_Freeze.
"""

import cx_Freeze
import distutils.command.install
import distutils.command.install_data
import distutils.sysconfig
import os
import sys

try:
    from setuptools import setup, Extension
    from setuptools.command.bdist_rpm import bdist_rpm as _bdist_rpm
    from setuptools.command.build_ext import build_ext as _build_ext
except ImportError:
    from distutils.core import setup
    from distutils.extension import Extension
    from distutils.command.bdist_rpm import bdist_rpm as _bdist_rpm
    from distutils.command.build_ext import build_ext as _build_ext

if sys.platform == "win32":
    import msilib
    from distutils.command.bdist_msi import bdist_msi as _bdist_msi

    class bdist_msi(_bdist_msi):

        def add_scripts(self):
            _bdist_msi.add_scripts(self)
            msilib.add_data(self.db, "RemoveFile",
                    [("cxFreezeBatch", "cx_Freeze", "cxfreeze*.bat", "Scripts",
                        2)])


class bdist_rpm(_bdist_rpm):

    # rpm automatically byte compiles all Python files in a package but we
    # don't want that to happen for initscripts and samples so we tell it to
    # ignore those files
    def _make_spec_file(self):
        specFile = _bdist_rpm._make_spec_file(self)
        specFile.insert(0, "%define _unpackaged_files_terminate_build 0%{nil}")
        return specFile

    def run(self):
        _bdist_rpm.run(self)
        specFile = os.path.join(self.rpm_base, "SPECS",
                "%s.spec" % self.distribution.get_name())
        queryFormat = "%{name}-%{version}-%{release}.%{arch}.rpm"
        command = "rpm -q --qf '%s' --specfile %s" % (queryFormat, specFile)
        origFileName = os.popen(command).read()
        parts = origFileName.split("-")
        parts.insert(2, "py%s%s" % sys.version_info[:2])
        newFileName = "-".join(parts)
        self.move_file(os.path.join("dist", origFileName),
                os.path.join("dist", newFileName))


class build_ext(_build_ext):

    def build_extension(self, ext):
        if "bases" not in ext.name:
            _build_ext.build_extension(self, ext)
            return
        if sys.platform == "win32" and self.compiler.compiler_type == "mingw32":
            ext.sources.append("source/bases/manifest.rc")
        os.environ["LD_RUN_PATH"] = "${ORIGIN}:${ORIGIN}/../lib"
        objects = self.compiler.compile(ext.sources,
                output_dir = self.build_temp,
                include_dirs = ext.include_dirs,
                debug = self.debug,
                depends = ext.depends)
        fileName = os.path.splitext(self.get_ext_filename(ext.name))[0]
        fullName = os.path.join(self.build_lib, fileName)
        libraryDirs = ext.library_dirs or []
        libraries = self.get_libraries(ext)
        extraArgs = ext.extra_link_args or []
        if sys.platform == "win32":
            compiler_type = self.compiler.compiler_type
            if compiler_type == "msvc":
                extraArgs.append("/MANIFEST")
                if "AsAdministrator" in ext.name:
                    extraArgs.append("/MANIFESTUAC:level='requireAdministrator' uiAccess='false'")
            elif compiler_type == "mingw32" and "Win32GUI" in ext.name:
                extraArgs.append("-mwindows")
        else:
            vars = distutils.sysconfig.get_config_vars()
            libraryDirs.append(vars["LIBPL"])
            abiflags = getattr(sys, "abiflags", "")
            libraries.append("python%s.%s%s" % \
                    (sys.version_info[0], sys.version_info[1], abiflags))
            if vars["LINKFORSHARED"] and sys.platform != "darwin":
                extraArgs.extend(vars["LINKFORSHARED"].split())
            if vars["LIBS"]:
                extraArgs.extend(vars["LIBS"].split())
            if vars["LIBM"]:
                extraArgs.append(vars["LIBM"])
            if vars["BASEMODLIBS"]:
                extraArgs.extend(vars["BASEMODLIBS"].split())
            if vars["LOCALMODLIBS"]:
                extraArgs.extend(vars["LOCALMODLIBS"].split())
            extraArgs.append("-s")
        self.compiler.link_executable(objects, fullName,
                libraries = libraries,
                library_dirs = libraryDirs,
                runtime_library_dirs = ext.runtime_library_dirs,
                extra_postargs = extraArgs,
                debug = self.debug)

    def get_ext_filename(self, name):
        fileName = _build_ext.get_ext_filename(self,
                name)
        if name.endswith("util"):
            return fileName
        vars = distutils.sysconfig.get_config_vars()
        soExt = vars.get("EXT_SUFFIX", vars.get("SO"))
        ext = self.compiler.exe_extension or ""
        return fileName[:-len(soExt)] + ext


def find_cx_Logging():
    dirName = os.path.dirname(os.getcwd())
    loggingDir = os.path.join(dirName, "cx_Logging")
    if not os.path.exists(loggingDir):
        return
    subDir = "implib.%s-%s" % (distutils.util.get_platform(), sys.version[:3])
    importLibraryDir = os.path.join(loggingDir, "build", subDir)
    if not os.path.exists(importLibraryDir):
        return
    return loggingDir, importLibraryDir


commandClasses = dict(
        build_ext = build_ext,
        bdist_rpm = bdist_rpm)
if sys.platform == "win32":
    commandClasses["bdist_msi"] = bdist_msi

# build utility module
if sys.platform == "win32":
    libraries = ["imagehlp", "Shlwapi"]
else:
    libraries = []
utilModule = Extension("cx_Freeze.util", ["source/util.c"],
        libraries = libraries)

# build base executables
docFiles = "README.txt"
scripts = ["cxfreeze", "cxfreeze-quickstart"]
options = dict(bdist_rpm = dict(doc_files = docFiles),
        install = dict(optimize = 1))
depends = ["source/bases/Common.c"]
console = Extension("cx_Freeze.bases.Console", ["source/bases/Console.c"],
        depends = depends, libraries = libraries)
extensions = [utilModule, console]
if sys.platform == "win32":
    scripts.append("cxfreeze-postinstall")
    options["bdist_msi"] = dict(install_script = "cxfreeze-postinstall")
    consoleAsAdministrator = Extension("cx_Freeze.bases.ConsoleAsAdministrator", ["source/bases/Console.c"],
            depends = depends, libraries = libraries)
    extensions.append(consoleAsAdministrator)
    gui = Extension("cx_Freeze.bases.Win32GUI", ["source/bases/Win32GUI.c"],
            depends = depends, libraries = libraries + ["user32"])
    extensions.append(gui)
    guiAsAdministrator = Extension("cx_Freeze.bases.Win32GUIAsAdministrator", ["source/bases/Win32GUI.c"],
            depends = depends, libraries = libraries + ["user32"])
    extensions.append(guiAsAdministrator)
    moduleInfo = find_cx_Logging()
    if moduleInfo is not None:
        includeDir, libraryDir = moduleInfo
        service = Extension("cx_Freeze.bases.Win32Service",
                ["source/bases/Win32Service.c"], depends = depends,
                library_dirs = [libraryDir],
                libraries = libraries + ["advapi32", "cx_Logging"],
                include_dirs = [includeDir])
        extensions.append(service)

# define package data
packageData = []
for fileName in os.listdir(os.path.join("cx_Freeze", "initscripts")):
    name, ext = os.path.splitext(fileName)
    if ext != ".py":
        continue
    packageData.append("initscripts/%s" % fileName)
for fileName in os.listdir(os.path.join("cx_Freeze", "samples")):
    dirName = os.path.join("cx_Freeze", "samples", fileName)
    if not os.path.isdir(dirName):
        continue
    packageData.append("samples/%s/*.py" % fileName)

classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Python Software Foundation License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: C",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Software Distribution",
        "Topic :: Utilities"
]

setup(name = "cx_Freeze",
        description = "create standalone executables from Python scripts",
        long_description = "create standalone executables from Python scripts",
        version = "5.1.1.dev0+x",
        cmdclass = commandClasses,
        options = options,
        ext_modules = extensions,
        packages = ['cx_Freeze'],
        maintainer="Anthony Tuininga",
        maintainer_email="anthony.tuininga@gmail.com",
        url = "https://anthony-tuininga.github.io/cx_Freeze",
        scripts = scripts,
        classifiers = classifiers,
        keywords = "freeze",
        license = "Python Software Foundation License",
        package_data = {"cx_Freeze" : packageData })

