#!/usr/bin/env python3
"""Paletli aracın görsel modelini (STL) CadQuery ile üretir.

Görünüm ve oranlar HAVELSAN BARKAN 3'e göre (2.7 x 1.5 m, ~1 t; fotoğraflardan
ölçülen palet/gövde oranları), 1 m sınırına ölçeklenmiş (x0.36 -> 0.98 x 0.55 m).
Palet: büyük arka tahrik dişlisi, önde avara (ikisi de yerden yüksekte), altta 6
çift yol tekeri, üstte taşıyıcı makara. Mesh'ler sadece görsel; çarpışmalar URDF'te
basit şekiller (ugv_description/urdf/ugv.urdf.xacro). Ölçüler araç tanımından
(ugv_description/config/vehicle.yaml) okunur; orada değişince mesh'leri yeniden üretin.

Çıktı (ugv_description/meshes/, metre, base_link = dişli dingili hizası):
  hull.stl        gövde, üst gövde, panel çıkıntıları             (base_link)
  hull_dark.stl   ön panel pencereleri, lambalar, direk, kamera    (base_link)
  track_belt.stl  palet bandı, pabuçlar, taşıyıcı makara           (<side>_track)
  sprocket.stl    arka tahrik dişlisi                             (<side>_sprocket)
  idler.stl       ön avara                                        (<side>_idler)
  road_wheel.stl  çift yol tekeri                                 (<side>_road_N)
Teker mesh'lerinin ekseni z (URDF teker eklemi z'yi yanal eksene çevirir).

Gereksinim (tek seferlik, repo dışında):
  python3 -m venv ~/.venvs/cadquery && ~/.venvs/cadquery/bin/pip install cadquery trimesh pyyaml

Kullanım:
  ~/.venvs/cadquery/bin/python tools/ugv_model.py src/ugv_description/meshes
"""
import argparse
import math
import os
import tempfile

import cadquery as cq
import numpy as np
import trimesh
import yaml

# ==================== ÖLÇÜLER (config/vehicle.yaml) ====================
VEHICLE_YAML = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'src', 'ugv_description', 'config', 'vehicle.yaml')
with open(VEHICLE_YAML, encoding='utf-8') as _f:
    _V = yaml.safe_load(_f)
_T, _H = _V['track'], _V['hull']

BASE_HEIGHT = _T['base_height']      # base_link yerden (dişli ve avara dingili)
BELT_T = _T['belt_thickness']        # bant kalınlığı (pabuç dahil); tekerler bandın iç yüzeyine değer
CLEAT_H = 0.007                      # pabuç yüksekliği (sadece görsel)
TRACK_WIDTH = _T['width']
TRACK_SEPARATION = _T['separation']  # palet merkezleri arası
SPROCKET = (_T['sprocket_x'], 0.0, _T['sprocket_radius'])   # x, z (base_link), dış yarıçap
IDLER = (_T['idler_x'], 0.0, _T['idler_radius'])
ROAD_R = _T['road_radius']           # yol tekeri (bant içi)
ROAD_Z = -BASE_HEIGHT + BELT_T + ROAD_R
ROAD_XS = tuple(_T['road_xs'])
RETURN_ROLLER_X = _T['return_roller_x']
HULL_Z = (_H['bottom'], _H['top'])   # yerden: gövde altı, güverte
UPPER_Z = _H['upper_bottom']         # üst gövde (paletlerin üstüne taşan kısım) altı, yerden
HULL_X = (_H['x0'], _H['x1'])
LOWER_HALF_W = _H['lower_width'] / 2  # paletler arası alt gövde
UPPER_HALF_W = _H['upper_width'] / 2


def g(z):
    """Yerden yüksekliği base_link z'sine çevirir."""
    return z - BASE_HEIGHT


def side_prism(points_xz, width, y=0.0):
    """(x, z) profilini y boyunca simetrik uzatır (XY'de çizip X etrafında döndürür)."""
    return (cq.Workplane('XY').polyline(points_xz).close()
            .extrude(width / 2, both=True)
            .rotate((0, 0, 0), (1, 0, 0), 90)
            .translate((0, y, 0)))


def box(cx, cy, cz, sx, sy, sz):
    return cq.Workplane('XY').box(sx, sy, sz).translate((cx, cy, cz))


def to_trimesh(shape):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'part.stl')
        cq.exporters.export(shape, path, tolerance=0.0005, angularTolerance=0.15)
        return trimesh.load(path)


def union_all(parts):
    out = parts[0]
    for p in parts[1:]:
        out = out.union(p)
    return out


# ==================== GÖVDE ====================
def hull():
    x0, x1 = HULL_X
    z0, z1 = HULL_Z
    # Alt gövde (paletler arası): önü pahlı
    lower = side_prism([
        (x0, g(z0)), (x1 - 0.07, g(z0)), (x1, g(0.20)), (x1, g(UPPER_Z)), (x0, g(UPPER_Z)),
    ], 2 * LOWER_HALF_W)
    # Üst gövde: paletlerin üstüne taşar; ön yüz eğimli, güverte kenarı pahlı
    upper = side_prism([
        (x0, g(UPPER_Z)), (x1, g(UPPER_Z)), (x1, g(0.30)), (x1 - 0.05, g(z1)),
        (x0 + 0.02, g(z1)), (x0, g(z1 - 0.02)),
    ], 2 * UPPER_HALF_W)
    parts = [lower, upper]
    # Güvertedeki panel çıkıntıları (kapaklar) ve yan panel nervürleri
    for cx, sx in ((-0.26, 0.20), (-0.03, 0.22), (0.20, 0.18)):
        parts.append(box(cx, 0, g(z1 + 0.006), sx, 0.34, 0.012))
    for s in (1, -1):
        for cx in (-0.30, -0.10, 0.10, 0.28):
            parts.append(box(cx, s * (UPPER_HALF_W + 0.004), g(0.30), 0.14, 0.008, 0.05))
        # Güverte köşelerinde bağlama halkası tabanları
        for cx in (-0.36, 0.34):
            parts.append(box(cx, s * 0.21, g(z1 + 0.012), 0.03, 0.03, 0.024))
    return union_all(parts)


def hull_dark():
    x1 = HULL_X[1]
    parts = []
    # Ön panel: sensör pencereleri ve lambalar
    for dy in (-0.16, 0.16):
        parts.append(box(x1 + 0.004, dy, g(0.285), 0.008, 0.06, 0.03))
    for dy in (-0.07, 0.07):
        parts.append(box(x1 + 0.004, dy, g(0.235), 0.008, 0.04, 0.04))
    # Sensör direği (arka sağ): direk, yükseltici kutu, çift lensli kamera kafası
    mx, my = -0.31, -0.17
    parts.append(box(mx, my, g(HULL_Z[1] + 0.05), 0.07, 0.07, 0.10))
    parts.append(cq.Workplane('XY').circle(0.018).extrude(0.78 - HULL_Z[1] - 0.10)
                 .translate((mx, my, g(HULL_Z[1] + 0.10))))
    parts.append(box(mx, my, g(0.82), 0.10, 0.13, 0.08).edges('|X').fillet(0.012))
    for dy in (0.035, -0.035):
        parts.append(cq.Workplane('YZ').circle(0.022).extrude(0.02)
                     .translate((mx + 0.05, my + dy, g(0.82))))
    return union_all(parts)


# ==================== PALET ====================
def convex_hull_2d(pts):
    """Andrew monotone chain; saat yönünün tersine köşe listesi."""
    pts = sorted(map(tuple, pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def belt_circles(offset=0.0):
    """Bant dış hattını belirleyen çemberler (x, z, r): dişli, avara, ilk/son yol tekeri."""
    road_outer = ROAD_R + BELT_T
    return [(SPROCKET[0], SPROCKET[1], SPROCKET[2] + offset),
            (IDLER[0], IDLER[1], IDLER[2] + offset),
            (ROAD_XS[0], ROAD_Z, road_outer + offset),
            (ROAD_XS[-1], ROAD_Z, road_outer + offset)]


def belt_outline(offset=0.0, n=96):
    pts = []
    for cx, cz, r in belt_circles(offset):
        for a in np.linspace(0, 2 * math.pi, n, endpoint=False):
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return convex_hull_2d(pts)


def resample(poly, step):
    """Kapalı çokgen üzerinde eşit aralıklı noktalar ve dış normaller."""
    poly = np.array(poly + [poly[0]])
    seg = np.diff(poly, axis=0)
    lens = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0], np.cumsum(lens)])
    out = []
    for s in np.arange(0, cum[-1], step):
        i = np.searchsorted(cum, s, side='right') - 1
        t = (s - cum[i]) / lens[i]
        p = poly[i] + seg[i] * t
        d = seg[i] / lens[i]
        out.append((p, np.array([d[1], -d[0]])))     # CCW için dış normal
    return out


def track_belt():
    # Bant pabuç yüksekliği kadar içeride; pabuçların dış yüzü çarpışma hattında (zemin teması)
    outer = (cq.Workplane('XY').polyline(belt_outline(-CLEAT_H)).close()
             .extrude(TRACK_WIDTH / 2, both=True))
    inner = (cq.Workplane('XY').polyline(belt_outline(-BELT_T)).close()
             .extrude(TRACK_WIDTH / 2 + 0.01, both=True))
    belt = outer.cut(inner).rotate((0, 0, 0), (1, 0, 0), 90)
    meshes = [to_trimesh(belt)]

    # Pabuçlar (grouser): dış yüzeyde eşit aralıklı
    for p, nrm in resample(belt_outline(), 0.032):
        b = trimesh.creation.box((0.014, TRACK_WIDTH + 0.004, CLEAT_H + 0.002))
        ang = math.atan2(nrm[1], nrm[0]) - math.pi / 2
        b.apply_transform(trimesh.transformations.rotation_matrix(-ang, [0, 1, 0]))
        b.apply_translation([p[0] - nrm[0] * CLEAT_H / 2, 0, p[1] - nrm[1] * CLEAT_H / 2])
        meshes.append(b)
    # Ortadaki kılavuz dişleri (iç yüzeyde, bant ortasında)
    for p, nrm in resample(belt_outline(-BELT_T), 0.05):
        b = trimesh.creation.box((0.016, 0.018, 0.016))
        ang = math.atan2(nrm[1], nrm[0]) - math.pi / 2
        b.apply_transform(trimesh.transformations.rotation_matrix(-ang, [0, 1, 0]))
        b.apply_translation([p[0] - nrm[0] * 0.006, 0, p[1] - nrm[1] * 0.006])
        meshes.append(b)

    # Taşıyıcı makara: üst bandın altında, gövdeye bağlı
    (sx, sz, sr), (ix, iz, ir) = SPROCKET, IDLER
    x = RETURN_ROLLER_X
    top_inner = (sz + sr - BELT_T) + (x - sx) * ((iz + ir) - (sz + sr)) / (ix - sx)
    r = 0.028
    roller = trimesh.creation.cylinder(radius=r, height=TRACK_WIDTH * 0.75, sections=32)
    roller.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    roller.apply_translation([x, 0, top_inner - r - 0.001])
    meshes.append(roller)
    return trimesh.util.concatenate(meshes)


# ==================== TEKERLER ====================
def spoked_disc(r, w, hub_r, n_holes, hole_r, hole_pcd):
    rim = cq.Workplane('XY').circle(r).circle(r - 0.012).extrude(w / 2, both=True)
    web = cq.Workplane('XY').circle(r - 0.012).extrude(0.006, both=True)
    hub = cq.Workplane('XY').circle(hub_r).extrude(w / 2, both=True)
    holes = (cq.Workplane('XY').workplane(offset=-w).polarArray(hole_pcd, 0, 360, n_holes)
             .circle(hole_r).extrude(2 * w))
    return rim.union(web).union(hub).cut(holes)


def sprocket():
    r = SPROCKET[2] - BELT_T
    w = TRACK_WIDTH * 0.75
    disc = cq.Workplane('XY').circle(r - 0.012).extrude(w / 2, both=True)
    teeth = (cq.Workplane('XY').polarArray(r - 0.006, 0, 360, 18)
             .rect(0.016, 0.02).extrude(w * 0.3, both=True))
    hub = cq.Workplane('XY').circle(0.03).extrude(w / 2 + 0.008, both=True)
    holes = (cq.Workplane('XY').workplane(offset=-w).polarArray(0.06, 0, 360, 8)
             .circle(0.016).extrude(2 * w))
    return disc.union(teeth).union(hub).cut(holes)


def idler():
    return spoked_disc(IDLER[2] - BELT_T, TRACK_WIDTH * 0.75, 0.025, 6, 0.014, 0.048)


def road_wheel():
    # Çift tekerlek: iki disk, ortada kılavuz dişleri için boşluk
    w = TRACK_WIDTH * 0.32
    gap = TRACK_WIDTH * 0.18
    one = spoked_disc(ROAD_R, w, 0.012, 6, 0.008, 0.027)
    axle = cq.Workplane('XY').circle(0.01).extrude(gap / 2 + w, both=True)
    return (one.translate((0, 0, gap / 2 + w / 2))
            .union(one.translate((0, 0, -gap / 2 - w / 2))).union(axle))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('out_dir')
    out = ap.parse_args().out_dir
    os.makedirs(out, exist_ok=True)
    parts = {
        'hull': lambda: to_trimesh(hull()),
        'hull_dark': lambda: to_trimesh(hull_dark()),
        'track_belt': track_belt,
        'sprocket': lambda: to_trimesh(sprocket()),
        'idler': lambda: to_trimesh(idler()),
        'road_wheel': lambda: to_trimesh(road_wheel()),
    }
    for name, make in parts.items():
        mesh = make()
        path = os.path.join(out, f'{name}.stl')
        mesh.export(path)
        lo, hi = mesh.bounds
        print(f'{name:11s} {len(mesh.faces):6d} yuz  x[{lo[0]:+.3f},{hi[0]:+.3f}] '
              f'y[{lo[1]:+.3f},{hi[1]:+.3f}] z[{lo[2]:+.3f},{hi[2]:+.3f}]')


if __name__ == '__main__':
    main()
