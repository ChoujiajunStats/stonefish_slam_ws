from setuptools import find_packages, setup
setup(name="uw_runtime", version="0.1.0", packages=find_packages(),
      data_files=[("share/ament_index/resource_index/packages", ["resource/uw_runtime"]),
                  ("share/uw_runtime", ["package.xml"])],
      install_requires=["setuptools"], zip_safe=True,
      license="LicenseRef-Not-Yet-Licensed")
