"""Install package."""

import setuptools
from pathlib import Path


# {'name': 'OctoPrint-PSUControl-Meross', 'version': '0.0.7.dev16', 'description': 'Adds Meross Smart Plug support to OctoPrint-PSUControl',
# 'author': 'Ilja Orlovs', 'author_email': 'vrghost@gmail.com', 'url': 'https://github.com/VRGhost/OctoPrint-PSUControl-Meross',
# 'license': 'AGPLv3', 'cmdclass': {'clean': <class 'octoprint_setuptools.CleanCommand'>, 'babel_new': <class 'octoprint_setuptools.NewTranslation'>,
# 'babel_extract': <class 'octoprint_setuptools.ExtractTranslation'>, 'babel_refresh': <class 'octoprint_setuptools.RefreshTranslation'>,
# 'babel_compile': <class 'octoprint_setuptools.CompileTranslation'>, 'babel_pack': <class 'octoprint_setuptools.PackTranslation'>,
# 'babel_bundle': <class 'octoprint_setuptools.BundleTranslation'>}, 'packages': {'octoprint_psucontrol_meross'},
# 'package_data': {'octoprint_psucontrol_meross': []}, 'include_package_data': True, 'zip_safe': False, 'install_requires': #
# ['meross-iot>=0.4', 'OctoPrint>=1.7.3'], 'extras_require': {}, 'dependency_links': [], 'entry_points': {'octoprint.plugin': ['psucontrol_meross = octoprint_psucontrol_meross']}}


setuptools.setup(
    name="OctoPrint-PSUControl-Meross",
    version="0.0.7.dev35",
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
    install_requires=["OctoPrint>=1.7.3", "meross-iot>=0.4"],
    python_requires=">=3.6",
)
