import os
from setuptools import find_packages, setup

package_name = 'ugv_web'


def www_data_files():
    # www altındaki statik dosyaları (HTML/CSS/JS) klasör yapısını koruyarak kopyala
    entries = []
    for root, _, files in os.walk(os.path.join(package_name, 'www')):
        if files:
            rel = os.path.relpath(root, package_name)
            entries.append((os.path.join('share', package_name, rel),
                            [os.path.join(root, f) for f in files]))
    return entries


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ] + www_data_files(),
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