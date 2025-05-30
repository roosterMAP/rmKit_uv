bl_info = {
	"name": "rmKitUV",
	"author": "Timothee Yeramian",
	"location": "View3D > Sidebar",
	"description": "Collection of Tools",
	"category": "",
	"blender": ( 3, 3, 1),
	"warning": "",
	"doc_url": "https://rmkit.readthedocs.io/en/latest/",
}

import bpy
from . import (
	propertygroup,
	move_to_furthest_uv,
	stitch,
	panel,
	loopringuv,
	gridify,
	relativeislands,
	uvtransform,
	unrotate,
	rectangularize,
	hotspot,
	uvboundstransform,
	uvgrowshrink,
	preferences,
	linear_deformer_uv,
	seambyangle
)

class rmKitUVPannel_parent( bpy.types.Panel ):
	bl_idname = "VIEW3D_PT_RMKITUV_PARENT"
	bl_label = "rmUV"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "rmUV"

	def draw( self, context ):
		layout = self.layout


class rmKitUVPannel_parent_uv( bpy.types.Panel ):
	bl_idname = "UV_PT_RMKITUV_PARENT"
	bl_label = "rmUV"
	bl_space_type = "IMAGE_EDITOR"
	bl_region_type = "UI"
	bl_category = "rmUV"

	def draw( self, context ):
		layout = self.layout

def register():
	bpy.utils.register_class( rmKitUVPannel_parent )
	bpy.utils.register_class( rmKitUVPannel_parent_uv )

	propertygroup.register()
	panel.register()

	loopringuv.register()
	move_to_furthest_uv.register()
	linear_deformer_uv.register()	
	stitch.register()
	gridify.register()
	relativeislands.register()
	unrotate.register()
	uvtransform.register()
	rectangularize.register()
	hotspot.register()
	uvboundstransform.register()
	uvgrowshrink.register()
	seambyangle.register()
	
	preferences.register()

def unregister():
	bpy.utils.unregister_class( rmKitUVPannel_parent )
	bpy.utils.unregister_class( rmKitUVPannel_parent_uv )

	propertygroup.unregister()
	panel.unregister()

	loopringuv.unregister()
	move_to_furthest_uv.unregister()
	linear_deformer_uv.unregister()
	stitch.unregister()
	gridify.unregister()
	relativeislands.unregister()
	unrotate.unregister()
	uvtransform.unregister()
	rectangularize.unregister()
	hotspot.unregister()
	uvboundstransform.unregister()
	uvgrowshrink.unregister()
	seambyangle.unregister()
	
	preferences.unregister()