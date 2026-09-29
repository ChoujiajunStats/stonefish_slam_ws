from glob import glob
from setuptools import find_packages, setup

setup(
    name="uw_robot", version="0.1.0", packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/uw_robot"]),
        ("share/uw_robot", ["package.xml"]),
        ("share/uw_robot/config", glob("config/*")),
    ],
    install_requires=["setuptools"], zip_safe=True,
    maintainer="Jiajun Zhou", maintainer_email="ChoujiajunStats@126.com",
    description="Underwater Stack M0 robot module",
    license="LicenseRef-Not-Yet-Licensed",
    entry_points={"console_scripts": []},
)
