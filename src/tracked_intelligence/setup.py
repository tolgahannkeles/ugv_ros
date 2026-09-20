from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'tracked_intelligence'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'models'), glob('models/*.onnx')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='tolgahan',
    maintainer_email='tolgahan@todo.todo',
    description='Vision-based intelligence and depth estimation for tracked UGV',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'depth_node = tracked_intelligence.depth_node:main',
            'avoidance_node = tracked_intelligence.avoidance_node:main',
        ],
    },
)
