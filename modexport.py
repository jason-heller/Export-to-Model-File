bl_info = {
    "name": ".MOD Export",
    "description": "Exports to proprietary .MOD format",
    "author": "Jason H",
    "version": (1, 0),
    "blender": (2, 65, 0),
    "location": "File > Import-Export",
    "warning": "", # used for warning icon and text in addons panel
    "doc_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/"
                "Scripts/My_Script",
    "tracker_url": "https://developer.blender.org/maniphest/task/edit/form/2/",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

import bpy
import array
import bmesh

from bpy.props import (
    BoolProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    )

from bpy_extras.io_utils import (
    ExportHelper,
    path_reference_mode,
    axis_conversion,
    )

def triangulate_object(obj):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method=0, ngon_method=0)
    bm.to_mesh(me)
    bm.free()

class ExportMOD(bpy.types.Operator, ExportHelper):

    bl_idname   = "export_scene_normals.mod"
    bl_label    = 'Export MOD'
    bl_options  = { 'PRESET' }

    filename_ext    = ".mod"
    filter_glob     = StringProperty(default = "*.mod", options = {'HIDDEN'},)
          
    def execute(self, context):
    
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode = 'OBJECT')
         
        scene = context.scene
        frame = scene.frame_current
        
        scene.frame_set(frame, 0.0)
        
        maxInfluence = 3                # Max number of bones allows to influence a single vertex
    
        print("Exporting to: " + self.filepath)
        f = open(self.filepath, "wb")

        magicNumber             = array.array('b', 'MOD4'.encode())
        magicNumber.tofile(f)
        numMeshes = array.array('b', [len(bpy.data.meshes)])
        numMeshes.tofile(f)
        
        for mesh in bpy.data.meshes:
        
            weightsUnsorted = []        # \ The weights and respective bones, in the same order as mesh.vertices
            bonesUnsorted   = []        # /
            
            objects     = []
            
            vertices    = []                # \ 
            texCoords   = []                # |
            normals     = []                # | .. Raw mesh data
            weights     = []                # | 
            bones       = []                # |
            indices     = []                # /
        
            print(mesh.name)
            nameLength = array.array('i', [len(mesh.name)])
            nameLength.tofile(f)
            meshName = array.array('b', mesh.name.encode())
            meshName.tofile(f)
            
            #set vertices
            
            for vertex in mesh.vertices:
                
                # Get a list of the non-zero group weightings for the vertex
                nonZero = []
                for g in vertex.groups:
                    
                    g.weight = round(g.weight, 4)
                    
                    if g.weight < .0001:
                        continue
                    
                    nonZero.append(g)

                # Sort them by weight decending
                byWeight = sorted(nonZero, key = lambda group: group.weight)
                byWeight.reverse()

                # As long as there are more than 'maxInfluence' bones, take the lowest influence bone
                # and distribute the weight to the other bones.
                while len(byWeight) > maxInfluence:

                    print("Distributing weight for vertex %d" % (vertex.index))

                    # Pop the lowest influence off and compute how much should go to the other bones.
                    minInfluence = byWeight.pop()
                    distributeWeight = minInfluence.weight / len(byWeight)
                    minInfluence.weight = 0

                    # Add this amount to the other bones        
                    for influence in byWeight:
                        influence.weight = influence.weight + distributeWeight

                    # Round off the remaining values.
                    for influence in byWeight:
                        influence.weight = round(influence.weight, 4)
                        
                for influence in byWeight:
                    weightsUnsorted.append(influence.weight)
                    bonesUnsorted.append(influence.group)
                    
                for x in range(len(byWeight) - 1, maxInfluence):
                    weightsUnsorted.append(0)
                    bonesUnsorted.append(0)

            # Vertices have a 1:1 relationship with texture coords, normals, weights, and bone IDs,
            # we must reorganize this data, as in blender texture coords exists w.r.t. faces
            newVertexArray      = []
            newTexCoordArray    = []
            
            currentIndex = -1
            
            for polygon in mesh.polygons:
            
                for j in range(0,3):
                
                    exists = False
                    currentIndex += 1
                
                    #for k in range(0, len(newVertexArray)):
                    
                    #    if newVertexArray[k] == polygon.vertices[j] and currentIndex == newTexCoordArray[k]:
                    #        indices.append(k)
                    #        exists = True
                    #        break
                    
                    if not exists:
                        newVertexArray.append(polygon.vertices[j])
                        newTexCoordArray.append(currentIndex)
                        indices.append(len(newVertexArray) - 1)
            
            """
                SET MESH DATA
            """
            for i in range(len(newVertexArray)):
                vertId = newVertexArray[i]
                texCoordId = newTexCoordArray[i]
                
                vertex = mesh.vertices[vertId]
                x = vertex.co.x
                y = vertex.co.y
                z = vertex.co.z
                vertices.extend([y, z, x])
                
                if mesh.uv_layers is None:                  # Hacky, should find better way to do this
                    texCoords.extend([0, 0]) 
                else:
                    texCoords.extend( mesh.uv_layers.active.data[texCoordId].uv ) 
                    
                normals.extend(vertex.normal)
    
                for inf in range(maxInfluence):
                    weights.append(weightsUnsorted[(vertId * maxInfluence) + inf])
                    bones.append(bonesUnsorted[(vertId * maxInfluence) + inf])

            """
                WRITE EVERYTHING TO FILE
            """
            objects.append(0)                               # materialId (placeholder)
            objects.append(len(vertices) // 3)              # numVertices
            objects.append(len(indices))                    # numFaces
            
            print(str(len(mesh.vertices)) + " vertices")
            print(str(len(mesh.polygons) * 3) + " indices") 
            
            objectsArray            = array.array('i', objects)
            verticesArray           = array.array('f', vertices)
            texCoordArray           = array.array('f', texCoords)
            normalsArray            = array.array('f', normals)
            weightsArray            = array.array('f', weights)
            bonesArray              = array.array('b', bones)
            indexArray              = array.array('i', indices)
            

            objectsArray.tofile(f)
            verticesArray.tofile(f)
            texCoordArray.tofile(f)
            normalsArray.tofile(f)
            weightsArray.tofile(f)
            bonesArray.tofile(f)
            indexArray.tofile(f)
            print(str(len(objectsArray)) + " (objectsArray length)")
            print(str(len(verticesArray)) + " (verticesArray length)")
            print(str(len(texCoordArray)) + " (texCoordArray length)")
            print(str(len(normalsArray)) + " (normalsArray length)")
            print(str(len(weightsArray)) + " (weightsArray length)")
            print(str(len(bonesArray)) + " (bonesArray length)")
            print(str(len(indexArray)) + " (indexArray length)")
        
        print("Writing armature data")
        """
            SET ARMATURE DATA
        """
        boneNames       = []
        boneNameOffests = []
        boneMatrices    = []
        boneParents     = []
        
        offset = 0
        # TODO: Find better way to do this
        rig = None # bpy.data.objects['Armature']
        for armature in [ob for ob in bpy.data.objects if ob.type == 'ARMATURE']:
            rig = armature
            break

        if rig is not None:
            
            boneNameOffests.append(len( rig.data.bones ))        # number of bones
        
            for x, b in enumerate(rig.data.bones):
                tempString = b.name
                tempList   = [ord(c) for c in tempString]
                boneNames.extend( tempList )
                boneNameOffests.append( offset )
                offset += len( tempList )
                boneNameOffests.append( len( tempList ) )
                
                for j in range(3):
                    for i in range(3):
                        boneMatrices.append( b.matrix[i][j] )
                
                parentid = -1
                if b.parent is not None:
                    parentid = rig.data.bones.find( b.parent.name )
                
                boneParents.append( parentid )
        
        boneNamesArray          = array.array('b', boneNames)
        boneNameOffestsArray    = array.array('i', boneNameOffests)
        boneParentsArray        = array.array('b', boneParents)
        boneMatricesArray       = array.array('f', boneMatrices)
        
        if rig is None:
            array.array('b', [0]).tofile(f)
            print("No armature found, skipping")
        else:
            array.array('b', [1]).tofile(f)
            boneNameOffestsArray.tofile(f)
            boneNamesArray.tofile(f)
            boneParentsArray.tofile(f)
            boneMatricesArray.tofile(f)
        f.close()
        return {'FINISHED'}
        
def menu_func_export(self, context):
    self.layout.operator(ExportMOD.bl_idname, text="Model (.mod)")
    
def register():
    bpy.utils.register_module(__name__)

    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
