import bpy, bmesh, mathutils
import rmlib


def uvedge_boundary( l, uvlayer ):
	#test if edge loop is a boundary of a uv island
	for f in l.edge.link_faces:
		if f == l.face:
			continue
		if edge_continuous( l.face, f, uvlayer ):
			return False		
	return True


def edge_continuous( f1, f2, uvlayer ):
	#test if two faces are conntected by an edge in uv space
	for l1 in f1.loops:
		for l2 in f2.loops:
			if l1.edge == l2.edge:
				if ( rmlib.util.AlmostEqual_v2( l1.link_loop_next[uvlayer].uv, l2[uvlayer].uv ) and
				rmlib.util.AlmostEqual_v2( l1[uvlayer].uv, l2.link_loop_next[uvlayer].uv ) ):
					return True
	return False

def uvedge_loop_fwd( loop, group, uvlayer, force_boundary=False ):
	nl = loop.link_loop_next
				
	#count uv edges coming out of nl
	uvedgecount = 0
	possible_edges = nl.vert.link_edges
	counted_edges = set()
	for f in nl.vert.link_faces:
		for l in f.loops:
			if l.edge not in possible_edges or l.edge in counted_edges:
				continue
			if l.vert == nl.vert:
				if rmlib.util.AlmostEqual_v2( l[uvlayer].uv, nl[uvlayer].uv ):
					if not uvedge_boundary( l, uvlayer ):
						counted_edges.add( l.edge )
					uvedgecount += 1
			else:
				if rmlib.util.AlmostEqual_v2( l.link_loop_next[uvlayer].uv, nl[uvlayer].uv ):
					if not uvedge_boundary( l, uvlayer ):
						counted_edges.add( l.edge )
					uvedgecount += 1
						
	if uvedgecount == 3 or uvedgecount == 4:
		if uvedge_boundary( nl, uvlayer ):
			return group
		for f in nl.edge.link_faces:
			if f == nl.face:
				continue
			for l in f.loops:

				if l.edge == nl.edge:
					next_loop = l.link_loop_next
					if next_loop.tag:
						continue
					if uvedgecount == 3 and not uvedge_boundary( next_loop, uvlayer ):
						continue
					next_loop.tag = True
					group.append( next_loop )
					uvedge_loop_fwd( next_loop, group, uvlayer, force_boundary )
		
	return group


def uvedge_loop_rev( loop, group, uvlayer, force_boundary=False ):	
	#count uv edges coming out of nl
	uvedgecount = 0
	possible_edges = loop.vert.link_edges
	counted_edges = set()
	for f in loop.vert.link_faces:
		for l in f.loops:
			if l.edge not in possible_edges or l.edge in counted_edges:
				continue
			if l.vert == loop.vert:
				if rmlib.util.AlmostEqual_v2( l[uvlayer].uv, loop[uvlayer].uv ):
					if not uvedge_boundary( l, uvlayer ):
						counted_edges.add( l.edge )
					uvedgecount += 1
			else:
				if rmlib.util.AlmostEqual_v2( l.link_loop_next[uvlayer].uv, loop[uvlayer].uv ):
					if not uvedge_boundary( l, uvlayer ):
						counted_edges.add( l.edge )
					uvedgecount += 1
										
	nl = loop.link_loop_prev
	if uvedgecount == 3 or uvedgecount == 4:
		if uvedge_boundary( nl, uvlayer ):
			return group
		for f in nl.edge.link_faces:
			if f == nl.face:
				continue
			for l in f.loops:
				if l.edge == nl.edge:
					prev_loop = l.link_loop_prev
					if prev_loop.tag:
						continue
					if uvedgecount == 3 and not uvedge_boundary( prev_loop, uvlayer ):
						continue
					prev_loop.tag = True
					group.append( prev_loop )
					uvedge_loop_rev( prev_loop, group, uvlayer, force_boundary )
		
	return group


def uvedge_ring( loop, group, uvlayer ):
	if len( loop.face.verts ) != 4:
		return group
	
	next_loop = loop.link_loop_next.link_loop_next
	if next_loop.tag:
		return group
	next_loop.tag = True
	group.append( next_loop )
	
	for f in next_loop.edge.link_faces:
		if f == next_loop.face:
			continue
		for l in f.loops:
			if l.edge == next_loop.edge and edge_continuous( f, next_loop.face, uvlayer ):
				next_loop = l
				if next_loop.tag:
					return group
				next_loop.tag = True
				group.append( next_loop )
				uvedge_ring( next_loop, group, uvlayer )
				
	return group


class MESH_OT_uvloop( bpy.types.Operator ):
	"""Extend current edge selection by loop. Utilizes 3DS Max algorithm."""
	bl_idname = 'mesh.rm_uvloop'
	bl_label = 'UV Loop Select'
	bl_options = { 'UNDO' }
	
	force_boundary: bpy.props.BoolProperty(
		name='Force Boundary',
		description='When True, all loop edges extend along bounary edges.',
		default=False
	)
	
	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'IMAGE_EDITOR' and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):		
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:			
			sel_sync = context.tool_settings.use_uv_select_sync
			if sel_sync:
				bpy.ops.mesh.rm_loop( force_boundary=self.force_boundary )
				
			else:				
				sel_mode = context.tool_settings.uv_select_mode
				if sel_mode != 'EDGE':
					bpy.ops.mesh.rm_uvring()
					return { 'FINISHED' }
				
				uvlayer = rmmesh.active_uv
			
				#clear loopm tags
				for f in rmmesh.bmesh.faces:
					for l in f.loops:
						l.tag = False
						
				#tag loop selection
				loop_selection = rmlib.rmUVLoopSet.from_edge_selection( rmmesh=rmmesh, uvlayer=uvlayer )
				for l in loop_selection:
					l.tag = True
					l[uvlayer].select_edge = False
				
				for l in loop_selection:					
					group = uvedge_loop_fwd( l, [ l ], uvlayer, self.force_boundary )
					group = uvedge_loop_rev( l, group, uvlayer, self.force_boundary )
					
					for l in group:
						l[uvlayer].select_edge = True
						uvcoord = mathutils.Vector( l[uvlayer].uv )
						for n_l in l.vert.link_loops:
							n_uvcoord = mathutils.Vector( n_l[uvlayer].uv )
							if rmlib.util.AlmostEqual_v2( uvcoord, n_uvcoord ):
								n_l[uvlayer].select = True
						uvcoord = mathutils.Vector( l.link_loop_next[uvlayer].uv )
						for n_l in l.link_loop_next.vert.link_loops:
							n_uvcoord = mathutils.Vector( n_l[uvlayer].uv )
							if rmlib.util.AlmostEqual_v2( uvcoord, n_uvcoord ):
								n_l[uvlayer].select = True
				
				for f in rmmesh.bmesh.faces:
					for l in f.loops:
						l.tag = False

		return { 'FINISHED' }


class MESH_OT_uvring( bpy.types.Operator ):
	"""Extend current edge selection by ring. Utilizes 3DS Max algorithm."""
	bl_idname = 'mesh.rm_uvring'
	bl_label = 'UV Ring Select'
	bl_options = { 'UNDO' }
	
	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'IMAGE_EDITOR' and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):		
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:			
			sel_sync = context.tool_settings.use_uv_select_sync
			if sel_sync:
				bpy.ops.mesh.rm_ring()
			else:				
				sel_mode = context.tool_settings.uv_select_mode
				if sel_mode == 'EDGE':				
					uvlayer = rmmesh.active_uv
				
					#clear tags
					for f in rmmesh.bmesh.faces:
						for l in f.loops:
							l.tag = False
							
					#tag selection
					loop_selection = rmlib.rmUVLoopSet.from_edge_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					for l in loop_selection:
						l.tag = True
						l[uvlayer].select_edge = False
					
					for l in loop_selection:								
						group = uvedge_ring( l, [ l ], uvlayer )
						
						for l in group:
							l[uvlayer].select_edge = True
							uvcoord = mathutils.Vector( l[uvlayer].uv )
							for n_l in l.vert.link_loops:
								n_uvcoord = mathutils.Vector( n_l[uvlayer].uv )
								if rmlib.util.AlmostEqual_v2( uvcoord, n_uvcoord ):
									n_l[uvlayer].select = True
							uvcoord = mathutils.Vector( l.link_loop_next[uvlayer].uv )
							for n_l in l.link_loop_next.vert.link_loops:
								n_uvcoord = mathutils.Vector( n_l[uvlayer].uv )
								if rmlib.util.AlmostEqual_v2( uvcoord, n_uvcoord ):
									n_l[uvlayer].select = True
					
					for f in rmmesh.bmesh.faces:
						for l in f.loops:
							l.tag = False


				elif sel_mode == 'FACE':					
					uvlayer = rmmesh.active_uv

					#clear tags
					for f in rmmesh.bmesh.faces:
						for l in f.loops:
							l.tag = False
							
					#tag selection
					loop_selection = rmlib.rmUVLoopSet.from_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					faces = set()
					for l in loop_selection:
						l.tag = True
						l[uvlayer].select = False
						faces.add( l.face )

					#get face selection
					face_selection = rmlib.rmPolygonSet()
					for f in faces:
						all_loops_tagged = True
						for l in f.loops:
							if not l.tag:
								all_loops_tagged = False
								break
						if all_loops_tagged:
							f.tag = True
							face_selection.append( f )

					loop_selection = rmlib.rmUVLoopSet( [], uvlayer=uvlayer )
					for f in face_selection:
						for l in f.loops:
							for nf in l.edge.link_faces:
								if nf != f and nf.tag:
									loop_selection.append( l )
									break

					#clear tags
					for f in rmmesh.bmesh.faces:
						for l in f.loops:
							l.tag = False

					#set tags
					for l in loop_selection:
						l.tag = True

					#gather ring selection			
					all_loops = set()
					for l in loop_selection:								
						all_loops |= set( uvedge_ring( l, [ l ], uvlayer ) )
						
					#select resulting face loops
					for l in all_loops:
						for nl in l.face.loops:
							nl[uvlayer].select = True
							nl[uvlayer].select_edge = True
							
					for l in all_loops:
						for nl in l.vert.link_loops:
							if nl[uvlayer].select:
								continue
							if rmlib.util.AlmostEqual_v2( l[uvlayer].uv, nl[uvlayer].uv ):
								nl[uvlayer].select = True
								
					for f in rmmesh.bmesh.faces:
						f.tag = False
						for l in f.loops:
							l.tag = False

		return { 'FINISHED' }


def register():
	bpy.utils.register_class( MESH_OT_uvloop )
	bpy.utils.register_class( MESH_OT_uvring )
	
	
def unregister():
	bpy.utils.unregister_class( MESH_OT_uvloop )
	bpy.utils.unregister_class( MESH_OT_uvring )