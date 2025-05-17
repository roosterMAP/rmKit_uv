import bpy, bmesh
import rmlib
import math


def edge_face_angle( edge ):
	if len( edge.link_faces ) != 2:
		return None
	
	l1, l2 = edge.link_loops
	f1 = l1.face
	f2 = l2.face
	v1 = l1.vert
	v2 = l2.vert
	
	n1 = f1.normal
	n2 = f2.normal		

	# Get edge direction ( tangent )
	edge_dir = ( v2.co - v1.co ).normalized()
	vec1 = edge_dir.cross( n1 ).normalized()
	vec2 = edge_dir.cross( n2 ).normalized()
	
	return rmlib.util.Angle2( vec1, vec2, edge_dir )


class MESH_OT_set_seams_by_angle( bpy.types.Operator ):
	"""Set Seam by Angle"""
	bl_idname = "mesh.rm_seambyangle"
	bl_label = "Set Seam by Angle"
	bl_options = {'REGISTER', 'UNDO'}

	angle_threshold: bpy.props.FloatProperty( 
		name="Angle Threshold",
		description="Signed angle threshold in degrees",
		default=math.radians( 30.0 ),
		min=0.0,
		max=math.pi,
		subtype='ANGLE'
	 )

	use_concave: bpy.props.BoolProperty( 
		name="Use Concave",
		description="Set seams for concave angles",
		default=True
	 )

	use_convex: bpy.props.BoolProperty( 
		name="Use Convex",
		description="Set seams for convex angles",
		default=False
	 )

	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'VIEW_3D' and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):
		obj = context.active_object
		if not obj or obj.type != 'MESH':
			self.report( {'ERROR'}, "Active object is not a mesh" )
			return {'CANCELLED'}

		bm = bmesh.from_edit_mesh( obj.data )
		bm.edges.ensure_lookup_table()

		for edge in bm.edges:
			if not edge.select:
				continue
				
			angle = edge_face_angle( edge )
			if angle is None:
				continue
				
			concave = self.angle_threshold <= abs( angle ) and angle < 0.0
			if self.use_concave and concave:
				edge.seam = True
			else:
				edge.seam = False

			convex = self.angle_threshold <= abs( angle ) and angle > 0.0
			if self.use_convex and convex:
				edge.seam = True

			if self.use_concave and self.use_convex:
				edge.seam = concave or convex

		bmesh.update_edit_mesh( obj.data )

		return {'FINISHED'}


def menu_func( self, context ):
	self.layout.operator( MESH_OT_set_seams_by_angle.bl_idname )


def register():
	bpy.utils.register_class( MESH_OT_set_seams_by_angle )
	bpy.types.VIEW3D_MT_edit_mesh_edges.append( menu_func )


def unregister():
	bpy.types.VIEW3D_MT_edit_mesh_edges.remove( menu_func )
	bpy.utils.unregister_class( MESH_OT_set_seams_by_angle )