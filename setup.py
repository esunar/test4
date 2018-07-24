import re
import setuptools
import warnings

warnings.simplefilter("ignore", UserWarning)  # Older pips complain about newer options.

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("debian/changelog", "r") as fh:
    version = re.search(r'\((.*)\)', fh.readline()).group(1)

setuptools.setup(
    name="juju-lint",
    version=version,
    author="Canonical",
    author_email="juju@lists.ubuntu.com",
    description="Linter for Juju models to compare deployments with configurable policy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://launchpad.net/juju-lint",
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Development Status :: 2 - Beta",
        "Environment :: Plugins",
        "Intended Audience :: System Administrators"),
    python_requires='>=3.4',
    py_modules=["jujulint"],
    entry_points={
        'console_scripts': [
            'juju-lint=jujulint:main']})
