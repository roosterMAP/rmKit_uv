import bpy, rna_keymap_ui

RM_MESH_KEYMAP = []
RM_UV_KEYMAP = []
RM_GUI_NAMES = set()

#https://docs.blender.org/api/current/bpy.types.KeyMapItems.html#bpy.types.KeyMapItems

def register_keyboard_keymap():
	kc = bpy.context.window_manager.keyconfigs.addon
	if kc:		
		km_mesh = kc.keymaps.new( name='Mesh', space_type='EMPTY' )
		km_uv = kc.keymaps.new( name='UV Editor', space_type='EMPTY' )

		#MESH KEYMAPS		
		RM_MESH_KEYMAP.append( ( km_mesh, km_mesh.keymap_items.new( 'mesh.matchhotspot', 'NONE', 'PRESS' ) ) )
		RM_MESH_KEYMAP.append( ( km_mesh, km_mesh.keymap_items.new( 'mesh.grabapplyuvbounds', 'NONE', 'PRESS' ) ) )
		RM_MESH_KEYMAP.append( ( km_mesh, km_mesh.keymap_items.new( 'object.savehotspot', 'NONE', 'PRESS' ) ) )
		RM_MESH_KEYMAP.append( ( km_mesh, km_mesh.keymap_items.new( 'mesh.rm_worldspaceproject', 'NONE', 'PRESS' ) ) )
		RM_MESH_KEYMAP.append( ( km_mesh, km_mesh.keymap_items.new( 'mesh.rm_seambyangle', 'NONE', 'PRESS' ) ) )


		#UV EDITOR KEYMAPS
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.moshotspot', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.nrsthotspot', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.matchhotspot', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'object.savehotspot', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvloop', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvring', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvrectangularize', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvgridify', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_relativeislands', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_stitch', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvunrotate', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_scaletomaterialsize', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_normalizetexels', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvboundstransform', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvaspectscale', 'NONE', 'PRESS' ) ) )
		RM_UV_KEYMAP.append( ( km_uv, km_uv.keymap_items.new( 'mesh.rm_uvfalloff', 'NONE', 'PRESS' ) ) )

		kmi = km_uv.keymap_items.new( 'wm.call_menu_pie', 'NONE', 'PRESS' )
		kmi.properties.name = 'IMAGE_EDITOR_MT_PIE_uvmovetofurthest'
		RM_GUI_NAMES.add( 'IMAGE_EDITOR_MT_PIE_uvmovetofurthest' )
		RM_UV_KEYMAP.append( ( km_uv, kmi ) )

		kmi = km_uv.keymap_items.new( 'mesh.rm_uvgrowshrink', 'NONE', 'PRESS' )
		kmi.properties.mode = 'GROW'
		RM_UV_KEYMAP.append( ( km_uv, kmi ) )

		kmi = km_uv.keymap_items.new( 'mesh.rm_uvgrowshrink', 'NONE', 'PRESS' )
		kmi.properties.mode = 'SHRINK'
		RM_UV_KEYMAP.append( ( km_uv, kmi ) )

		kmi = km_uv.keymap_items.new( 'wm.call_menu_pie', 'NONE', 'PRESS' )
		kmi.properties.name = 'VIEW3D_MT_PIE_uvquicklineardeform'
		RM_GUI_NAMES.add( 'VIEW3D_MT_PIE_uvquicklineardeform' )
		RM_UV_KEYMAP.append( ( km_uv, kmi ) )


def unregister_keyboard_keymap():
	for km, kmi in RM_MESH_KEYMAP:
		km.keymap_items.remove( kmi )
	for km, kmi in RM_UV_KEYMAP:
		km.keymap_items.remove( kmi )
	RM_MESH_KEYMAP.clear()
	RM_UV_KEYMAP.clear()
	RM_GUI_NAMES.clear()


class RMKITUVPreferences( bpy.types.AddonPreferences ):
	bl_idname = __package__

	mesh_checkbox: bpy.props.BoolProperty( name="Mesh", default=False )
	uv_checkbox: bpy.props.BoolProperty( name="UV Editor", default=False )

	def draw( self, context ):
		layout = self.layout

		box = layout.box()

		row_mesh = box.row()
		row_mesh.prop( self, 'mesh_checkbox', icon='TRIA_DOWN' if self.mesh_checkbox else 'TRIA_RIGHT', icon_only=True, emboss=False )
		row_mesh.label( text='Mesh' )
		if self.mesh_checkbox:
			col = box.column( align=True )
			self.draw_keymap_items( col, 'Mesh', RM_MESH_KEYMAP, {'ACTIONZONE', 'KEYBOARD', 'MOUSE', 'NDOF'}, False )

		row_uv = box.row()
		row_uv.prop( self, 'uv_checkbox', icon='TRIA_DOWN' if self.uv_checkbox else 'TRIA_RIGHT', icon_only=True, emboss=False )
		row_uv.label( text='UV Editor' )
		if self.uv_checkbox:
			col = box.column( align=True )
			self.draw_keymap_items( col, 'UV Editor', RM_UV_KEYMAP, {'ACTIONZONE', 'KEYBOARD', 'MOUSE', 'NDOF'}, False )

	@staticmethod
	def draw_keymap_items( col, km_name, keymap, map_type, allow_remove=False ):
		kc = bpy.context.window_manager.keyconfigs.user
		km = kc.keymaps.get( km_name )
		kmi_idnames = [ km_tuple[1].idname for km_tuple in keymap ]
		if allow_remove:
			col.context_pointer_set( 'keymap', km )

		for kmi in km.keymap_items:
			if kmi.idname in kmi_idnames and kmi.map_type in map_type:
				if kmi.idname == 'wm.call_menu_pie' or kmi.idname == 'wm.call_menu':
					if kmi.properties.name not in RM_GUI_NAMES:
						continue
				rna_keymap_ui.draw_kmi( ['ADDON', 'USER', 'DEFAULT'], kc, km, kmi, col, 0 )
		

def register():
	bpy.utils.register_class( RMKITUVPreferences )
	register_keyboard_keymap()


def unregister():
	bpy.utils.unregister_class( RMKITUVPreferences )
	unregister_keyboard_keymap()