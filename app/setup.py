from glob import glob
from setuptools import find_packages, setup

setup(
    name="uw_app", version="0.1.0", packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/uw_app"]),
        ("share/uw_app", ["package.xml"]),
        ("share/uw_app/launch", glob("launch/*.py")),
    ],
    install_requires=["setuptools"], zip_safe=True,
    maintainer="Jiajun Zhou", maintainer_email="ChoujiajunStats@126.com",
    description="Underwater Stack M0 app module",
    license="LicenseRef-Not-Yet-Licensed",
    entry_points={"console_scripts": ['run = uw_app.runner:main', 'm2_run = uw_app.m2_runner:main', 'm3_run = uw_app.m3_runner:main']},
)
