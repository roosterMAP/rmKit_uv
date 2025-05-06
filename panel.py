import bpy
import rmlib
		

class UV_PT_UVTOOLS( bpy.types.Panel ):
	bl_parent_id = 'UV_PT_RMKITUV_PARENT'
	bl_idname = 'UV_PT_UVTOOLS'
	bl_label = 'UV Operations'
	bl_region_type = 'UI'
	bl_space_type = 'IMAGE_EDITOR'
	bl_options = { 'HIDE_HEADER' }

	def draw( self, context ):
		layout = self.layout

		r1 = layout.row()
		r1.alignment = 'EXPAND'
		r1.operator( 'mesh.rm_uvloop', text='UV Loop' )
		r1.operator( 'mesh.rm_uvring', text='UV Ring' )
		
		layout.operator( 'wm.call_menu_pie', text='UV Move To Furthest' ).name = 'IMAGE_EDITOR_MT_PIE_uvmovetofurthest'
		if bpy.app.version < ( 4, 0, 0 ):
			layout.operator( 'mesh.rm_uvboundstransform', text='Bounds Transform' )
		layout.operator( 'mesh.rm_uvfalloff', text='Falloff UV Transform' )
		layout.operator( 'mesh.rm_uvaspectscale', text='Inset Scale UVs' )
		layout.operator( 'mesh.rm_uvgridify', text='Gridify' )
		layout.operator( 'mesh.rm_uvrectangularize', text='Boxify' )
		layout.operator( 'mesh.rm_stitch', text='Stitch' )
		layout.operator( 'mesh.rm_uvunrotate', text='Unrotate' )
		layout.operator( 'mesh.rm_relativeislands' )
		layout.operator( 'mesh.rm_worldspaceproject' )
		layout.operator( 'mesh.rm_scaletomaterialsize' )
		r3 = layout.row()
		r3.operator( 'mesh.rm_uvgrowshrink', text='UV Grow' ).mode = 'GROW'
		r3.operator( 'mesh.rm_uvgrowshrink', text='UV Shrink' ).mode = 'SHRINK'

		r2 = layout.row()
		r2.alignment = 'EXPAND'
		r2.operator( 'mesh.rm_normalizetexels', text='NmlTex U' ).horizontal = True
		r2.operator( 'mesh.rm_normalizetexels', text='NmlTex V' ).horizontal = False


class VIEW3D_PT_VIEW3D_UV( bpy.types.Panel ):
	bl_idname = 'VIEW3D_PT_VIEW3D_UV'
	bl_parent_id = 'VIEW3D_PT_RMKITUV_PARENT'
	bl_label = 'View3D UV Tools'
	bl_region_type = 'UI'
	bl_space_type = 'VIEW_3D'
	bl_options = { 'HIDE_HEADER' }

	def draw( self, context ):
		layout = self.layout

		layout.operator( 'mesh.rm_worldspaceproject' )
		layout.operator( 'mesh.rm_uvgridify', text='UV Gridify' )
		layout.operator( 'mesh.rm_uvrectangularize', text='UV Boxify' )
		layout.separator()
		layout.operator( 'object.savehotspot', text='New Hotspot' )
		layout.operator( 'mesh.refhotspot', text='Ref Hotspot' )
		layout.separator()
		r1 = layout.row()
		r1.prop( context.scene, 'use_multiUV' )
		r2 = layout.row()
		r2.prop( context.scene, 'hotspot_uv1' )
		r2.prop( context.scene, 'hotspot_uv2' )
		r2.enabled = context.scene.use_multiUV
		layout.operator( 'mesh.matchhotspot' )
	
	
def register():
	bpy.utils.register_class( UV_PT_UVTOOLS )
	bpy.utils.register_class( VIEW3D_PT_VIEW3D_UV )
	

def unregister():
	bpy.utils.unregister_class( UV_PT_UVTOOLS )
	bpy.utils.unregister_class( VIEW3D_PT_VIEW3D_UV )