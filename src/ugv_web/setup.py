import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'ugv_web'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # www klasöründeki tüm statik dosyaları (HTML/JS) kopyala
        (os.path.join('share', package_name, 'www'), glob('ugv_web/www/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='raspi',
    maintainer_email='raspi@todo.todo',
    description='Web GUI and video streaming bridge for UGV',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'web_server = ugv_web.web_server:main',
        ],
    },
)