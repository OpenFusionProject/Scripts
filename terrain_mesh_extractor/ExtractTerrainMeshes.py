from unitypackff.asset import Asset
from unitypackff.environment import UnityEnvironment
import bpy
import bmesh
import os

dongpath = r'C:\Users\gents\AppData\LocalLow\Unity\Web Player\Cache\Fusionfall'
env = UnityEnvironment(base_path=dongpath)
outpath = r'C:\Users\gents\3D Objects\FFTerrainMeshes'

def rip_terrain_mesh(f, outpath):
    dong = Asset.from_file(f, environment=env)

    for k, v in dong.objects.items():
        if v.type == 'TerrainData':
            terrainData = dong.objects[k].read()
            terrain_width = terrainData['m_Heightmap']['m_Width'] - 1
            terrain_height = terrainData['m_Heightmap']['m_Height'] - 1
            scale_x = terrainData['m_Heightmap']['m_Scale']['x']
            scale_z = terrainData['m_Heightmap']['m_Scale']['z']
            scale_y = terrainData['m_Heightmap']['m_Scale']['y']

            # create the terrain
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=terrain_width, y_subdivisions=terrain_height, size=128, enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
            context = bpy.context
            grid = context.edit_object

            # apply triangulate modifier
            mod = grid.modifiers.new("Triangulate", 'TRIANGULATE')
            mod.quad_method = 'FIXED' # triangle orientation
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.modifier_apply(modifier="Triangulate")

            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(context.edit_object.data)
            bm.verts.ensure_lookup_table()
            for index, height in enumerate(terrainData['m_Heightmap']['m_Heights']):
                # scale height
                height_norm = height / (2 ** 15 - 2)
                bm.verts[index].co.z = height_norm * scale_y
                # pivot and scale x
                bm.verts[index].co.x += terrain_width / 2
                bm.verts[index].co.x *= scale_x
                # pivot and scale z
                bm.verts[index].co.y += terrain_height / 2
                bm.verts[index].co.y *= scale_z
                #print(f"{bm.verts[index].co.x}, {bm.verts[index].co.y}, {bm.verts[index].co.z}")

            indices = []
            shift_amt = abs(bm.verts[0].co.x - bm.verts[1].co.x)
            # gather m_Shifts positions
            for shift in terrainData['m_Heightmap']['m_Shifts']:
                shift_index = shift['y'] + shift['x'] * 129
                indices.append(shift_index)
                v = bm.verts[shift_index]
                flags = shift['flags'] # bits: +X -X +Y -Y
                if flags & 0b1000: # +X
                    v.co.x += shift_amt
                if flags & 0b0100: # -X
                    v.co.x -= shift_amt
                if flags & 0b0010: # +Y
                    v.co.y += shift_amt
                if flags & 0b0001: # -Y
                    v.co.y -= shift_amt

            # flip diagonally
            for v in bm.verts:
                tmp = v.co.x
                v.co.x = v.co.y
                v.co.y = tmp

            # flip normals
            for f in bm.faces:
                f.normal_flip()

            # export
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action='SELECT')
            name = terrainData['m_Name']
            outfile = f"{name}.fbx"
            bpy.ops.export_scene.fbx(filepath=os.path.join(outpath, outfile))

            # select modified vertices
            #bpy.ops.object.mode_set(mode="EDIT")
            #bm = bmesh.from_edit_mesh(context.edit_object.data)
            #bm.verts.ensure_lookup_table()
            #for v in bm.verts:
            #    v.select = False
            #for shift_index in indices:
            #    v = bm.verts[shift_index]
            #    v.select = True
            
            # clear the scene
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()

dongs = os.listdir(dongpath)
for dongname in dongs:
    if not dongname.endswith("resourceFile"):
        continue
    assets = os.listdir(os.path.join(dongpath, dongname))
    for assetname in assets:
        if not assetname.startswith("CustomAssetBundle"):
            continue
        with open(os.path.join(dongpath, dongname, assetname), "rb") as f:
            outdir = os.path.join(outpath, dongname, assetname)
            os.makedirs(outdir, exist_ok=True)
            rip_terrain_mesh(f, outdir)