from setuptools import setup,find_packages
setup(name='uw_perception',version='0.2.0',packages=find_packages(),data_files=[('share/ament_index/resource_index/packages',['resource/uw_perception']),('share/uw_perception',['package.xml'])],install_requires=['setuptools'],entry_points={'console_scripts':['sensors = uw_perception.node:main']})
