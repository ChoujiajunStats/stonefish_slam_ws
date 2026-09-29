from glob import glob
from setuptools import setup,find_packages
setup(name='uw_navigation',version='0.1.0',packages=find_packages(),
 data_files=[('share/ament_index/resource_index/packages',['resource/uw_navigation']),('share/uw_navigation',['package.xml']),('share/uw_navigation/config',glob('config/*.yaml'))],
 install_requires=['setuptools'],zip_safe=True,maintainer='Jiajun Zhou',maintainer_email='ChoujiajunStats@126.com',
 description='M3 navigation',license='LicenseRef-Not-Yet-Licensed',entry_points={'console_scripts':['tracker = uw_navigation.node:main']})
