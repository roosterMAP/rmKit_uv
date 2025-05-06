import mathutils
import rmlib
import bpy, bmesh


def GetUnsyncUVVisibleFaces( rmmesh, sel_mode ):
	visible_faces = rmlib.rmPolygonSet()
	if sel_mode[0]:		
		for f in rmmesh.bmesh.faces:
			if f.hide:
				continue
			visible = True
			for v in f.verts:
				if not v.select:
					visible = False
					break
			if visible:
				visible_faces.append( f )
	elif sel_mode[1]:
		for f in rmmesh.bmesh.faces:
			if f.hide:
				continue
			visible = True
			for e in f.edges:
				if not e.select:
					visible = False
					break
			if visible:
				visible_faces.append( f )
	else:
		visible_faces = rmlib.rmPolygonSet.from_selection( rmmesh )
		
	return visible_faces


class MESH_OT_uvmovetofurthest( bpy.types.Operator ):
	"""Align selection to a uv axis most aligned with a direction relative to viewport camera."""
	bl_idname = 'mesh.rm_uvmovetofurthest'
	bl_label = 'UV Move To Furthest'
	bl_options = { 'UNDO' }

	str_dir: bpy.props.EnumProperty(
		items=[ ( "up", "Up", "", 1 ),
				( "down", "Down", "", 2 ),
				( "left", "Left", "", 3 ),
				( "right", "Right", "", 4 ),
				( "horizontal", "Horizontal", "", 5 ),
				( "vertical", "Vertical", "", 6 ) ],
		name="Direction",
		default="right"
	)

	local: bpy.props.BoolProperty(
		name='Local',
		description='Group selection based on 3d continuity and align each respectively.',
		default=False
	)

	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'IMAGE_EDITOR' and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):
		if context.object is None or context.mode == 'OBJECT':
			return { 'CANCELLED' }

		rmmesh = rmlib.rmMesh.GetActive( context )
		if rmmesh is None:
			return { 'CANCELLED' }
		
		with rmmesh as rmmesh:
			rmlib.clear_tags( rmmesh.bmesh )

			uvlayer = rmmesh.active_uv

			loop_groups = []

			sel_mode = context.tool_settings.mesh_select_mode[:]
			
			sel_sync = context.tool_settings.use_uv_select_sync
			if sel_sync:
				if sel_mode[0]:
					vert_selection = rmlib.rmVertexSet.from_selection( rmmesh )
					loop_selection = rmlib.rmUVLoopSet( vert_selection.loops, uvlayer=uvlayer )
					if self.local:
						loop_groups += loop_selection.group_vertices()
					else:
						loop_groups.append( loop_selection )

				elif sel_mode[1]:
					edge_selection = rmlib.rmEdgeSet.from_selection( rmmesh )
					loop_selection = rmlib.rmUVLoopSet( edge_selection.vertices.loops, uvlayer=uvlayer )
					if self.local:
						loop_groups += loop_selection.group_vertices()
					else:
						loop_groups.append( loop_selection )

				elif sel_mode[2]:
					face_selection = rmlib.rmPolygonSet.from_selection( rmmesh )
					loopset = set()
					for f in face_selection:
						loopset |= set( f.loops )
					loop_selection = rmlib.rmUVLoopSet( loopset, uvlayer=uvlayer )
					if self.local:
						loop_groups += loop_selection.group_vertices()
					else:
						loop_groups.append( loop_selection )

			else:
				visible_faces = GetUnsyncUVVisibleFaces( rmmesh, sel_mode )
				uv_sel_mode = context.tool_settings.uv_select_mode
				if uv_sel_mode == 'VERTEX':
					loop_selection = rmlib.rmUVLoopSet.from_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					visible_loop_selection = rmlib.rmUVLoopSet( uvlayer=uvlayer )
					for l in loop_selection:
						if l.face in visible_faces:
							visible_loop_selection.append( l )
					if self.local:
						loop_groups += visible_loop_selection.group_vertices()
					else:
						loop_groups.append( visible_loop_selection )
					
				elif uv_sel_mode == 'EDGE':
					loop_selection = rmlib.rmUVLoopSet.from_edge_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					visible_loop_selection = rmlib.rmUVLoopSet( uvlayer=uvlayer )
					for l in loop_selection:
						if l.face in visible_faces:
							visible_loop_selection.append( l )
					if self.local:
						loop_groups = visible_loop_selection.group_edges()
						for i in range( len( loop_groups ) ):
							loop_groups[i].add_overlapping_loops( True )
					else:
						loop_groups.append( visible_loop_selection )
						loop_groups[0].add_overlapping_loops( True )

				else: #FACE mode
					loop_selection = rmlib.rmUVLoopSet.from_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					visible_loop_selection = rmlib.rmUVLoopSet( uvlayer=uvlayer )
					for l in loop_selection:
						if l.face in visible_faces:
							visible_loop_selection.append( l )
					if self.local:
						loop_groups += loop_selection.group_faces()
					else:
						loop_groups.append( visible_loop_selection )
				
			for g in loop_groups:
				min_u = 99999999.9
				min_v = 99999999.9
				max_u = -99999999.9
				max_v = -99999999.9
				for l in g:
					u, v = l[uvlayer].uv
					if u < min_u:
						min_u = u
					if u > max_u:
						max_u = u
					if v < min_v:
						min_v = v
					if v > max_v:
						max_v = v
						
				avg_u = ( min_u + max_u ) * 0.5
				avg_v = ( min_v + max_v ) * 0.5
				
				for l in g:
					u, v = l[uvlayer].uv
					if self.str_dir == 'up':
						l[uvlayer].uv = ( u, max_v )
					elif self.str_dir == 'down':
						l[uvlayer].uv = ( u, min_v )
					elif self.str_dir == 'left':
						l[uvlayer].uv = ( min_u, v )
					elif self.str_dir == 'right':
						l[uvlayer].uv = ( max_u, v )
					elif self.str_dir == 'vertical':
						l[uvlayer].uv = ( u, avg_v )
					elif self.str_dir == 'horizontal':
						l[uvlayer].uv = ( avg_u, v )
					else:
						continue

			rmlib.clear_tags( rmmesh.bmesh )
			
		return { 'FINISHED' }


class IMAGE_EDITOR_MT_PIE_uvmovetofurthest( bpy.types.Menu ):
	"""Align selection to a uv axis most aligned with a direction relative to viewport camera."""
	bl_idname = 'IMAGE_EDITOR_MT_PIE_uvmovetofurthest'
	bl_label = 'UV Move To Furthest'

	def draw( self, context ):
		layout = self.layout

		pie = layout.menu_pie()
		op_l = pie.operator( 'mesh.rm_uvmovetofurthest', text='Left' )
		op_l.str_dir = 'left'
		op_l.local = context.object.mtfuv_prop_off
		
		op_r = pie.operator( 'mesh.rm_uvmovetofurthest', text='Right' )
		op_r.str_dir = 'right'
		op_r.local = context.object.mtfuv_prop_off
		
		op_d = pie.operator( 'mesh.rm_uvmovetofurthest', text='Down' )
		op_d.str_dir = 'down'
		op_d.local = context.object.mtfuv_prop_off
		
		op_u = pie.operator( 'mesh.rm_uvmovetofurthest', text='Up' )
		op_u.str_dir = 'up'
		op_u.local = context.object.mtfuv_prop_off

		pie.separator()
		
		pie.operator( 'wm.call_menu_pie', text='Local' ).name = 'IMAGE_EDITOR_MT_PIE_uvmovetofurthest_local'
		
		op_h = pie.operator( 'mesh.rm_uvmovetofurthest', text='Horizontal' )
		op_h.str_dir = 'vertical'
		op_h.local = context.object.mtfuv_prop_off
				
		op_v = pie.operator( 'mesh.rm_uvmovetofurthest', text='Vertical' )
		op_v.str_dir = 'horizontal'
		op_v.local = context.object.mtfuv_prop_off


class IMAGE_EDITOR_MT_PIE_uvmovetofurthest_local( bpy.types.Menu ):
	"""Align selection to a uv axis most aligned with a direction relative to viewport camera."""
	bl_idname = 'IMAGE_EDITOR_MT_PIE_uvmovetofurthest_local'
	bl_label = 'UV Move To Furthest LOCAL'

	def draw( self, context ):
		layout = self.layout

		pie = layout.menu_pie()
		op_l = pie.operator( 'mesh.rm_uvmovetofurthest', text='Left' )
		op_l.str_dir = 'left'
		op_l.local = context.object.mtfuv_prop_on
		
		op_r = pie.operator( 'mesh.rm_uvmovetofurthest', text='Right' )
		op_r.str_dir = 'right'
		op_r.local = context.object.mtfuv_prop_on
		
		op_d = pie.operator( 'mesh.rm_uvmovetofurthest', text='Down' )
		op_d.str_dir = 'down'
		op_d.local = context.object.mtfuv_prop_on
		
		op_u = pie.operator( 'mesh.rm_uvmovetofurthest', text='Up' )
		op_u.str_dir = 'up'
		op_u.local = context.object.mtfuv_prop_on
		
		pie.separator()
		
		pie.separator()
		
		op_h = pie.operator( 'mesh.rm_uvmovetofurthest', text='Horizontal' )
		op_h.str_dir = 'vertical'
		op_h.local = context.object.mtfuv_prop_on
				
		op_v = pie.operator( 'mesh.rm_uvmovetofurthest', text='Vertical' )
		op_v.str_dir = 'horizontal'
		op_v.local = context.object.mtfuv_prop_on


def register():
	bpy.utils.register_class( MESH_OT_uvmovetofurthest )
	bpy.utils.register_class( IMAGE_EDITOR_MT_PIE_uvmovetofurthest )
	bpy.utils.register_class( IMAGE_EDITOR_MT_PIE_uvmovetofurthest_local )
	bpy.types.Object.mtfuv_prop_on = bpy.props.BoolProperty( default=True	)
	bpy.types.Object.mtfuv_prop_off = bpy.props.BoolProperty( default=False )	
	

def unregister():
	bpy.utils.unregister_class( MESH_OT_uvmovetofurthest )
	bpy.utils.unregister_class( IMAGE_EDITOR_MT_PIE_uvmovetofurthest )
	bpy.utils.unregister_class( IMAGE_EDITOR_MT_PIE_uvmovetofurthest_local )
	del bpy.types.Object.mtfuv_prop_on
	del bpy.types.Object.mtfuv_prop_off
