from setuptools import setup, find_packages
from src.constants import version

setup(
    name="EZPeakFinder",
    version=version,
    author="YNZ",
    description="EZPeakFinder",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/YNZjp/EZPeakFinder",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "requests", "numpy", "scipy", "matplotlib", "PyQt5", "beautifulsoup4"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    entry_points={
        "console_scripts": [
            "ezpeakfinder=main:main",
        ],
    },
)
