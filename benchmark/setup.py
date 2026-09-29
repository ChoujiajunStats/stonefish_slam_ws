from glob import glob
from setuptools import find_packages, setup

setup(
    name="uw_benchmark", version="0.1.0", packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/uw_benchmark"]),
        ("share/uw_benchmark", ["package.xml"]),
    ],
    install_requires=["setuptools"], zip_safe=True,
    maintainer="Jiajun Zhou", maintainer_email="ChoujiajunStats@126.com",
    description="Underwater Stack M0 benchmark module",
    license="LicenseRef-Not-Yet-Licensed",
    entry_points={"console_scripts": ['m0_probe = uw_benchmark.probe:main', 'm1_case = uw_benchmark.m1_case:main', 'm1_observation = uw_benchmark.m1_observation:main', 'm2_case = uw_benchmark.m2_case:main', 'm3_case = uw_benchmark.m3_case:main', 'porth_case = uw_benchmark.porth_case:main', 'survey_case = uw_benchmark.survey_case:main']},
)
