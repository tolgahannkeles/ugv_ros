"""Araç tanımını (config/vehicle.yaml) launch dosyalarına açan yardımcı.

Launch dosyaları bu modülü share/ugv_description/launch'tan yükler:
    sys.path.insert(0, os.path.join(get_package_share_directory('ugv_description'), 'launch'))
    import vehicle
"""
import os

import yaml
from ament_index_python.packages import get_package_share_directory


def vehicle_path():
    return os.path.join(get_package_share_directory('ugv_description'), 'config', 'vehicle.yaml')


def load():
    with open(vehicle_path(), encoding='utf-8') as f:
        return yaml.safe_load(f)


def diff_drive_params(include_slip=True):
    """diff_drive_controller'ın araca bağlı parametreleri (controllers.yaml'da yok).

    include_slip=False: kayma çarpanını verme (gerçek robot kendi ölçtüğünü
    ugv_bringup/config/controllers_real.yaml'dan alır).
    """
    v = load()
    d, t = v['drive'], v['track']
    params = {
        'wheel_separation': t['separation'],
        'wheel_radius': t['sprocket_radius'],
        'linear.x.max_velocity': d['max_linear_velocity'],
        'linear.x.min_velocity': -d['max_linear_velocity'],
        'linear.x.max_acceleration': d['max_linear_acceleration'],
        'linear.x.min_acceleration': -d['max_linear_acceleration'],
        'angular.z.max_velocity': d['max_angular_velocity'],
        'angular.z.min_velocity': -d['max_angular_velocity'],
        'angular.z.max_acceleration': d['max_angular_acceleration'],
        'angular.z.min_acceleration': -d['max_angular_acceleration'],
    }
    if include_slip:
        params['wheel_separation_multiplier'] = d['wheel_separation_multiplier']
    return params


def spawner_args(params):
    """Parametreleri spawner'ın --controller-ros-args'ına çevirir (dosyadakileri ezer).

    Kısa biçim '-p' kullanılamaz: spawner onu kendi -p (param dosyası) seçeneği sanıyor.
    """
    args = []
    for name, value in params.items():
        args += ['--controller-ros-args', f'--param {name}:={float(value)}']
    return args
