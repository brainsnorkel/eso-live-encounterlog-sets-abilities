#!/usr/bin/env python3
"""
Setup script for ESO Live Encounter Log Sets & Abilities Analyzer
"""

from setuptools import setup, find_packages
import os

# Read version
exec(open("version.py").read())

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="eso-live-encounterlog-sets-abilities",
    version=__version__,
    author="Christopher Gentle",
    author_email="christopher.gentle@example.com",
    description="A cross-platform CLI tool for analyzing ESO encounter logs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/christophergentle/eso-live-encounterlog-sets-abilities",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Games/Entertainment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "eso-analyzer=eso_analyzer:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["setsdb/*.xlsx", "example-log/*.log"],
    },
    zip_safe=False,
)
