from glob import glob
from setuptools import find_packages, setup

setup(
    name="uw_simulations", version="0.1.0", packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/uw_simulations"]),
        ("share/uw_simulations", ["package.xml"]),
        ("share/uw_simulations/scenarios", glob("scenarios/*")),
    ],
    install_requires=["setuptools"], zip_safe=True,
    maintainer="Jiajun Zhou", maintainer_email="ChoujiajunStats@126.com",
    description="Underwater Stack M0 simulations module",
    license="LicenseRef-Not-Yet-Licensed",
    entry_points={"console_scripts": ['observation_adapter = uw_simulations.observation_node:main', 'actuator_adapter = uw_simulations.actuator_node:main', 'm2_debug_truth = uw_simulations.truth_node:main']},
)
