"""Install package."""

import setuptools
from pathlib import Path


setuptools.setup(
    name="OctoPrint-PSUControl-Meross",
    version="0.13.3",
    description="Adds Meross Smart Plug support to OctoPrint-PSUControl",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[],
    license="AGPLv3",
    author="Ilja Orlovs",
    author_email="vrghost@gmail.com",
    url="https://github.com/VRGhost/OctoPrint-PSUControl-Meross",
    package_dir={"": "src"},
    zip_safe=False,
    include_package_data=True,
    packages=setuptools.find_packages(where="src"),
    py_modules=[
        "octoprint_psucontrol_meross",
    ],
    entry_points={
        "octoprint.plugin": ["psucontrol_meross = octoprint_psucontrol_meross"]
    },
    install_requires=["OctoPrint>=1.7.3", "meross-iot>=0.4.6.0"],
    python_requires=">=3.7.3",
)
