#!/usr/bin/env python3
"""TEKNOFEST İKA parkur STEP dosyasını Gazebo (Harmonic) modeline çevirir.

STEP (SolidWorks, mm, Y-yukarı) -> kategori başına STL mesh'ler (m, Z-yukarı) + model.sdf

STEP'te renk yok (hepsi SolidWorks varsayılanı); renkler ürün adından atanır
(ör. "plastik bariyer kırmızı"). Cıvata/somun/rulman gibi küçük parçalar atılır.

Çarpışma:
  - zemin, rampalar, çakıllı yol, su geçişi : gerçek geometri
  - bariyer, duba, direk, engebe, kapı çerçevesi : parça başına dışbükey gövde (hafif)
  - tabela plakaları, zemin çizgileri, perde şeritleri : çarpışmasız (perde itilerek geçilir)

Gereksinim (tek seferlik, repo dışında):
  python3 -m venv ~/.venvs/cad && ~/.venvs/cad/bin/pip install cadquery-ocp trimesh rtree scipy

Kullanım:
  ~/.venvs/cad/bin/python tools/parkur_to_gazebo.py teknofest_parkur/<dosya>.STEP \\
      src/ugv_gazebo/models/teknofest_ika_parkur
"""
import argparse
import os
import re
import tempfile
from collections import defaultdict

import numpy as np
import trimesh

# ==================== KATEGORİLER ====================
# (ad, eşleşme regex'i, renk RGBA, çarpışma: 'mesh' | 'hull' | None)
CATEGORIES = [
    ('ground',        r'^PRK26-',                       (0.72, 0.58, 0.42, 1.0), 'mesh'),
    ('barrier_red',   r'^plastik bariyer k',            (0.85, 0.06, 0.06, 1.0), 'hull'),
    ('barrier_white', r'^plastik bariyer beyaz',        (0.95, 0.95, 0.95, 1.0), 'hull'),
    ('ramps',         r'^(Dik egim|Yan egim|Dik engel)', (0.62, 0.62, 0.64, 1.0), 'mesh'),
    ('gravel',        r'^Taşlı Çakıllı Yol',            (0.25, 0.25, 0.26, 1.0), 'mesh'),
    ('water',         r'^Sudan gecis',                  (0.35, 0.75, 0.90, 0.55), 'mesh'),
    ('cones',         r'^Traffic Cone',                 (1.00, 0.42, 0.00, 1.0), 'hull'),
    ('sign_plates',   r'^(İKA6-A-001-002|İKA7-A-001-001)', (0.96, 0.96, 0.96, 1.0), None),
    ('sign_posts',    r'^(İKA6-A-001-001|İKA7-A-001-002)', (0.08, 0.08, 0.08, 1.0), 'hull'),
    ('bumps',         r'^İKA4-',                        (0.10, 0.10, 0.10, 1.0), 'hull'),
    ('lines',         r'^HZ26-',                        (0.05, 0.05, 0.05, 1.0), None),
    ('curtain',       r'^KYR26-A-001-005',              (0.05, 0.05, 0.05, 1.0), None),
    ('frames',        r'^(KYR26-|SD26-)',         (0.15, 0.15, 0.16, 1.0), 'hull'),
]
MIN_PART_SIZE = 0.15  # m; daha küçük parçalar (cıvata, rulman, dişli...) atılır

# SolidWorks/glTF Y-yukarı -> Gazebo Z-yukarı: X etrafında +90°
Y_UP_TO_Z_UP = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])


def step_to_glb(step_path, glb_path, deflection_mm):
    """STEP'i XCAF ile okuyup ürün adlı düğümlerle GLB'ye yazar (m, Y-yukarı)."""
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString, TCollection_AsciiString
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.RWGltf import RWGltf_CafWriter
    from OCP.RWMesh import RWMesh_CoordinateSystem, RWMesh_NameFormat
    from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString
    from OCP.Message import Message_ProgressRange

    doc = TDocStd_Document(TCollection_ExtendedString('doc'))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    if reader.ReadFile(step_path) != 1:
        raise RuntimeError(f'STEP okunamadi: {step_path}')
    reader.Transfer(doc)

    shape = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()).GetOneShape()
    BRepMesh_IncrementalMesh(shape, deflection_mm, False, 0.5, True)

    writer = RWGltf_CafWriter(TCollection_AsciiString(glb_path), True)
    conv = writer.ChangeCoordinateSystemConverter()
    conv.SetInputLengthUnit(0.001)  # mm -> m
    conv.SetInputCoordinateSystem(RWMesh_CoordinateSystem.RWMesh_CoordinateSystem_Yup)
    writer.SetNodeNameFormat(RWMesh_NameFormat.RWMesh_NameFormat_Product)
    writer.SetMeshNameFormat(RWMesh_NameFormat.RWMesh_NameFormat_Product)
    writer.SetMergeFaces(True)
    writer.Perform(doc, IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString(),
                   Message_ProgressRange())


def classify(name):
    base = re.sub(r'_\d+$', '', name)
    for cat, pattern, _, _ in CATEGORIES:
        if re.match(pattern, base):
            return cat
    return None


def load_parts(glb_path):
    """Dünya koordinatında (m, Z-yukarı) parçaları kategoriye göre döndürür."""
    scene = trimesh.load(glb_path, force='scene')
    parts = defaultdict(list)
    dropped = defaultdict(int)
    for node in scene.graph.nodes_geometry:
        transform, geom = scene.graph[node]
        mesh = scene.geometry[geom].copy()
        mesh.apply_transform(Y_UP_TO_Z_UP @ transform)
        cat = classify(node)
        # Zemin çizgileri kalınlıksızdır; diğer küçük parçalar bağlantı elemanıdır
        if cat is None or (cat not in ('lines',) and mesh.extents.max() < MIN_PART_SIZE):
            dropped[re.sub(r'_\d+$', '', node)] += 1
            continue
        parts[cat].append(mesh)
    return parts, dropped


def material_xml(rgba):
    r, g, b, a = rgba
    return (f'<material><ambient>{r} {g} {b} 1</ambient><diffuse>{r} {g} {b} 1</diffuse>'
            f'<specular>0.1 0.1 0.1 1</specular></material>'
            + (f'<transparency>{1 - a:.2f}</transparency>' if a < 1 else ''))


def build(parts, out_dir):
    mesh_dir = os.path.join(out_dir, 'meshes')
    os.makedirs(mesh_dir, exist_ok=True)
    visuals, collisions, report = [], [], []

    for cat, _, rgba, coll in CATEGORIES:
        if not parts.get(cat):
            continue
        meshes = parts[cat]
        visual = trimesh.util.concatenate(meshes)
        visual.export(os.path.join(mesh_dir, f'{cat}.stl'))
        uri = f'model://teknofest_ika_parkur/meshes/{cat}.stl'
        visuals.append(
            f'      <visual name="{cat}">\n'
            f'        <geometry><mesh><uri>{uri}</uri></mesh></geometry>\n'
            f'        {material_xml(rgba)}\n'
            f'      </visual>')

        n_coll = 0
        if coll == 'mesh':
            n_coll = len(visual.faces)
            coll_uri = uri
        elif coll == 'hull':
            hull = trimesh.util.concatenate([m.convex_hull for m in meshes])
            hull.export(os.path.join(mesh_dir, f'{cat}_collision.stl'))
            n_coll = len(hull.faces)
            coll_uri = f'model://teknofest_ika_parkur/meshes/{cat}_collision.stl'
        if coll:
            collisions.append(
                f'      <collision name="{cat}">\n'
                f'        <geometry><mesh><uri>{coll_uri}</uri></mesh></geometry>\n'
                f'      </collision>')
        report.append((cat, len(meshes), len(visual.faces), n_coll))

    sdf = f'''<?xml version="1.0"?>
<!-- tools/parkur_to_gazebo.py ile uretildi; elle degistirmeyin, araci yeniden calistirin. -->
<sdf version="1.9">
  <model name="teknofest_ika_parkur">
    <static>true</static>
    <link name="parkur">
{chr(10).join(visuals)}
{chr(10).join(collisions)}
    </link>
  </model>
</sdf>
'''
    with open(os.path.join(out_dir, 'model.sdf'), 'w', encoding='utf-8') as f:
        f.write(sdf)
    with open(os.path.join(out_dir, 'model.config'), 'w', encoding='utf-8') as f:
        f.write('''<?xml version="1.0"?>
<model>
  <name>teknofest_ika_parkur</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <description>TEKNOFEST Insansiz Kara Araci parkuru (PRK26-A-001-001-00), STEP'ten donusturuldu.</description>
</model>
''')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', help='Parkur STEP dosyası')
    ap.add_argument('out_dir', help='Çıktı model klasörü (ör. src/ugv_gazebo/models/teknofest_ika_parkur)')
    ap.add_argument('--deflection', type=float, default=10.0, help='Mesh hassasiyeti (mm, varsayılan 10)')
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        glb = os.path.join(tmp, 'parkur.glb')
        print('STEP okunuyor ve meshleniyor...', flush=True)
        step_to_glb(args.step, glb, args.deflection)
        parts, dropped = load_parts(glb)

    report = build(parts, args.out_dir)
    print(f'\n{"kategori":15s} {"parca":>6s} {"ucgen":>8s} {"carpisma":>9s}')
    for cat, n, tris, coll in report:
        print(f'{cat:15s} {n:6d} {tris:8d} {coll if coll else "-":>9}')
    print(f'\natilan kucuk parca: {sum(dropped.values())} ({len(dropped)} tur)')
    print(f'cikti: {args.out_dir}')


if __name__ == '__main__':
    main()
