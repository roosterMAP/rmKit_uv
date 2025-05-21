import bpy

class HotspotProperties( bpy.types.PropertyGroup ):
	hs_use_clipboard_atlas: bpy.props.BoolProperty(
		name='Override With Clipboard Atlas',
		default=False,
		description='Use the overrice subrect atlas instead the material driven one.'
	)
	hs_hotspot_inset: bpy.props.FloatProperty(
		name='Inset',
		default=0.0
	)
	hs_recttype_filter: bpy.props.EnumProperty(
		name='Filter',
		default='none',
		items=[ ( 'none', 'None', "", 1 ),
				( 'onlytrim', 'Only Trims', "", 2 ),
				( 'notrim', 'No Trims', "", 3 ) ],
		description='Filter the subrects by type.'
	)
	hs_use_multiUV: bpy.props.BoolProperty(
		name='Use MultiUV',
		default=False
	)
	hs_hotspot_uv1: bpy.props.EnumProperty(
		items=[ ( "none", "None", "", 1 ),
				( "hotspot", "Repo", "", 2 ),
				( "clipboard", "Clipboard", "", 3 ),
				( "worldspace", "Worldspace", "", 4 ) ],
		name="UV1",
		default="hotspot"
	)
	hs_hotspot_uv2: bpy.props.EnumProperty(
		items=[ ( "none", "None", "", 1 ),
				( "hotspot", "Repo", "", 2 ),
				( "clipboard", "Clipboard", "", 3 ),
				( "worldspace", "Worldspace", "", 4 ) ],
		name="UV2",
		default="none"
	)
	hs_random_rotation: bpy.props.BoolProperty(
		name='Random Rotation',
		default=False,
		description='Randomly rotate the hotspot.'
	)
	hs_random_flip: bpy.props.BoolProperty(
		name='Random Flip',
		default=False,
		description='Randomly flip the hotspot.'
	)


class MoveToFurthestUVProperties( bpy.types.PropertyGroup ):
	mtfuv_prop_on = bpy.props.BoolProperty( default=True )
	mtfuv_prop_off = bpy.props.BoolProperty( default=False )


class UVTransformProps( bpy.types.PropertyGroup ):
	uv_uvmove_offset: bpy.props.FloatProperty( name='Offset', default=1.0 )
	uv_uvrotation_offset: bpy.props.FloatProperty( name='RotationOffset', default=90.0, min=0.0, max=180.0 )
	uv_uvscale_factor: bpy.props.FloatProperty( name='Offset', default=2.0 )
	anchor_val_prev: bpy.props.StringProperty( name='Anchor Prev Val', default='uv_anchor_c' )
	state_val_prev: bpy.props.StringProperty( name='State Prev Val', default='' )
	uv_fit_aspect: bpy.props.BoolProperty( name='Use Aspect', default=False )
	uv_fit_moveto: bpy.props.BoolProperty( name='Move To', default=True )
	uv_fit_bounds_min: bpy.props.FloatVectorProperty( size=2, default=( 0.0, 0.0 ) )
	uv_fit_bounds_max: bpy.props.FloatVectorProperty( size=2, default=( 1.0, 1.0 ) )
	uv_fit_movecontinuous: bpy.props.BoolProperty( name='Transform Continuous', default=False )

class RMKitUVSceneProperties(bpy.types.PropertyGroup):
	# Properties from move_to_furthest_uv.py
	movetofurthestuvprops: bpy.props.PointerProperty( type=MoveToFurthestUVProperties )

	# Properties from hotspot.py
	hotspotprops: bpy.props.PointerProperty( type=HotspotProperties )

	# Properties from uvtransform.py
	uvtransformprops: bpy.props.PointerProperty( type=UVTransformProps )


def register():
	bpy.utils.register_class( UVTransformProps )
	bpy.utils.register_class(HotspotProperties)
	bpy.utils.register_class(MoveToFurthestUVProperties)
	bpy.utils.register_class(RMKitUVSceneProperties)
	bpy.types.Scene.rmkituv_props = bpy.props.PointerProperty(type=RMKitUVSceneProperties)
	
def unregister():
	bpy.utils.unregister_class( UVTransformProps )
	bpy.utils.unregister_class(HotspotProperties)
	bpy.utils.unregister_class(MoveToFurthestUVProperties)
	bpy.utils.unregister_class(RMKitUVSceneProperties)
	del bpy.types.Scene.rmkituv_props