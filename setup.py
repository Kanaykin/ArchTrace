from setuptools import setup, find_packages

setup(
    name="ArchTrace",
    version="0.1",
    packages=find_packages(),
    install_requires=[],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "archtrace=ArchTrace.main:main",
        ],
    },
) 