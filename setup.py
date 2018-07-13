import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="juju-lint",
    version="1.0.0.dev1",
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
