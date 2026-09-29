from setuptools import setup, find_packages
from glob import glob
setup(name='uw_guard',version="0.1.0",packages=find_packages(),
 data_files=[("share/ament_index/resource_index/packages",["resource/uw_guard"]),
 ("share/uw_guard",["package.xml"]),("share/uw_guard/config",glob("config/*.yaml"))],
 install_requires=["setuptools"],zip_safe=True,maintainer="Jiajun Zhou",
 maintainer_email="ChoujiajunStats@126.com",description="M1 guard",
 license="LicenseRef-Not-Yet-Licensed",entry_points={"console_scripts":['guard = uw_guard.node:main', 'control_cli = uw_guard.cli:main']})
