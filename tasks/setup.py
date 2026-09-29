from glob import glob
from setuptools import setup,find_packages
setup(name='uw_tasks',version='0.1.0',packages=find_packages(),
 data_files=[('share/ament_index/resource_index/packages',['resource/uw_tasks']),('share/uw_tasks',['package.xml']),('share/uw_tasks/config',glob('config/*.yaml'))],
 install_requires=['setuptools'],zip_safe=True,maintainer='Jiajun Zhou',maintainer_email='ChoujiajunStats@126.com',
 description='M3 tasks',license='LicenseRef-Not-Yet-Licensed',entry_points={'console_scripts':['missions = uw_tasks.node:main', 'mission_cli = uw_tasks.cli:main']})
