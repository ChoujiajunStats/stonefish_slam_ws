from setuptools import setup, find_packages
from glob import glob
setup(name='uw_controller',version="0.1.0",packages=find_packages(),
 data_files=[("share/ament_index/resource_index/packages",["resource/uw_controller"]),
 ("share/uw_controller",["package.xml"]),("share/uw_controller/config",glob("config/*.yaml"))],
 install_requires=["setuptools"],zip_safe=True,maintainer="Jiajun Zhou",
 maintainer_email="ChoujiajunStats@126.com",description="M1 controller",
 license="LicenseRef-Not-Yet-Licensed",entry_points={"console_scripts":['body_velocity = uw_controller.node:main']})
