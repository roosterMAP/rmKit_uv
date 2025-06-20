import bpy, mathutils
import rmlib
import math, random, sys
import numpy as np

def shortest_path( source, end_verts, verts ):
	for v in verts:
		v.tag = True

	#fill dist_lookup with max values
	dist_lookup = {}
	for v in verts:
		dist_lookup[v] = sys.float_info.max
	dist_lookup[source] = 0.0

	innerSet = set( [ v for v in end_verts ] )

	#expand and fill dist_lookup until an end vert is found
	current = source
	while len( innerSet ) > 0:
		nearest_neighbor = None
		smallest_tentative_dist = sys.float_info.max
		for ne in current.link_edges:
			neighbor = ne.other_vert( current )
			if not neighbor.tag:
				continue
			dist = ( mathutils.Vector( current.co ) - mathutils.Vector( neighbor.co ) ).length
			tentative_dist = dist_lookup[current] + dist
			if tentative_dist < dist_lookup[neighbor]:
				dist_lookup[neighbor] = tentative_dist
			else:
				tentative_dist = dist_lookup[neighbor]
			if tentative_dist < smallest_tentative_dist:
				smallest_tentative_dist = tentative_dist
				nearest_neighbor = neighbor
		if nearest_neighbor is None:
			break
		current.tag = False
		current = nearest_neighbor
		if current in innerSet:
			innerSet.remove( current )

	min_dist = sys.float_info.max
	nearest_end_vert = None
	for nv in end_verts:
		if dist_lookup[nv] < min_dist:
			min_dist = dist_lookup[nv]
			nearest_end_vert = nv
	if nearest_end_vert is None:
		return []

	#go backwards to find the shortest path
	current = nearest_end_vert
	shortest_path = []
	while current != source:
		min_dist = sys.float_info.max
		prev_neighbor = None
		for ne in current.link_edges:
			neighbor = ne.other_vert( current )
			if neighbor.tag:
				continue
			try:
				if dist_lookup[neighbor] < min_dist and dist_lookup[neighbor] < dist_lookup[current]:
					min_dist = dist_lookup[neighbor]
					prev_neighbor = neighbor
			except KeyError:
				continue
		shortest_path.append( current )	
		if prev_neighbor is None:
			break
		current = prev_neighbor
	shortest_path.append( source )

	for v in verts:
		v.tag = False

	return shortest_path[::-1]


def next_boundary_loop( loop ):
	next_loop = loop.link_loop_next
	while not is_boundary( next_loop ):
		l = next_loop
		next_loop = None
		for other_f in l.edge.link_faces:
			if other_f != l.face:
				break
		for nl in other_f.loops:
			if nl.edge == l.edge:
				next_loop = nl.link_loop_next
				break
		if next_loop is None:
			next_loop = l
			break
	return next_loop


def prev_boundary_loop( loop ):
	prev_loops = [ loop.link_loop_prev ]
	prev_loop = prev_loops[0]
	while not is_boundary( prev_loop ):
		l = prev_loop
		prev_loop = None
		for other_f in l.edge.link_faces:
			if other_f != l.face:
				break
		for nl in other_f.loops:
			if nl.edge == l.edge:
				prev_loop = nl.link_loop_prev
				prev_loops.append( prev_loop )
				break
		if prev_loop is None:
			prev_loop = l
			break
	return prev_loops


def sort_loop_chain( loops ):
	#sorts the loops by the "flow" of the winding of the member faces.
	for l in loops:
		l.tag = True

	sorted_loops = [ loops[0] ]
	loops[0].tag = False
	for i in range( 1, len( loops ) ):

		#append to end
		nl = next_boundary_loop( sorted_loops[-1] )
		if nl.tag:
			nl.tag = False
			sorted_loops.append( nl )

		#insert to start
		pls = prev_boundary_loop( sorted_loops[0] )
		pl = pls[-1]
		if pl.tag:
			pl.tag = False
			sorted_loops.insert( 0, pl )

		if len( sorted_loops ) >= len( loops ):
			break
		
	return rmlib.rmUVLoopSet( sorted_loops, uvlayer=loops.uvlayer )


def BBoxFromPoints( points ):
	bbmin = mathutils.Vector( ( 99999.0, 99999.0 ) )
	bbmax = mathutils.Vector( ( -99999.0, -99999.0 ) )
	for i in range( len( points ) ):
		bbmin[0] = min( bbmin[0], points[i][0] )
		bbmin[1] = min( bbmin[1], points[i][1] )
		bbmax[0] = max( bbmax[0], points[i][0] )
		bbmax[1] = max( bbmax[1], points[i][1] )
	if ( bbmax[0] - bbmin[0] ) <= rmlib.util.FLOAT_EPSILON or ( bbmax[1] - bbmin[1] ) <= rmlib.util.FLOAT_EPSILON:
		bbmin = mathutils.Vector( ( 0.0, 0.0 ) )
		bbmax = mathutils.Vector( ( 1.0, 1.0 ) )
	return bbmin, bbmax


def FitToBBox( faces, initial_bbmin, initial_bbmax, uvlayer, uniform=False ):
	final_uvcoords = []
	for f in faces:
		for l in f.loops:
			final_uvcoords.append( l[uvlayer].uv.copy() )
	final_bbmin, final_bbmax = BBoxFromPoints( final_uvcoords )

	trans_mat = mathutils.Matrix.Identity( 3 )
	trans_mat[0][2] = ( initial_bbmin[0] + initial_bbmax[0] ) * 0.5
	trans_mat[1][2] = ( initial_bbmin[1] + initial_bbmax[1] ) * 0.5

	trans_mat_inv = mathutils.Matrix.Identity( 3 )
	trans_mat_inv[0][2] = ( final_bbmin[0] + final_bbmax[0] ) * -0.5
	trans_mat_inv[1][2] = ( final_bbmin[1] + final_bbmax[1] ) * -0.5

	scl_mat = mathutils.Matrix.Identity( 3 )
	initial_width = initial_bbmax[0] - initial_bbmin[0]
	initial_height = initial_bbmax[1] - initial_bbmin[1]
	initial_aspect = initial_height / initial_width
	target_bounds_width = initial_bbmax[0] - initial_bbmin[0]
	target_bounds_height = target_bounds_width * initial_aspect
	final_width = final_bbmax[0] - final_bbmin[0]
	final_height = final_bbmax[1] - final_bbmin[1]
	'''
	final_aspect = final_height / final_width
	if  ( final_aspect <= 1.0 and initial_aspect > 1.0 ) or ( final_aspect > 1.0 and initial_aspect <= 1.0 ):
		temp = final_width
		final_width = final_height
		final_height = temp
	'''
	scl_mat[0][0] = target_bounds_width / final_width
	scl_mat[1][1] = target_bounds_height / final_height

	if uniform:
		scl_mat[1][1] = scl_mat[0][0]

	mat = trans_mat @ scl_mat @ trans_mat_inv
	for f in faces:
		for l in f.loops:
			uv = mathutils.Vector( l[uvlayer].uv.copy() ).to_3d()
			uv[2] = 1.0
			uv = mat @ uv
			l[uvlayer].uv = uv.to_2d()


def GetPinCornersByAngle( sorted_boundary_loops, uvlayer ):
	sorted_tuples = []
	lcount = len( sorted_boundary_loops )
	for i, l in enumerate( sorted_boundary_loops ):
		prev_l = sorted_boundary_loops[i-1]
		next_l = sorted_boundary_loops[(i+1)%lcount]

		#compute angle between prev_l and next_l
		v1 = ( mathutils.Vector( prev_l[uvlayer].uv ) - mathutils.Vector( l[uvlayer].uv ) ).normalized()
		v2 = ( mathutils.Vector( next_l[uvlayer].uv ) - mathutils.Vector( l[uvlayer].uv ) ).normalized()
		theta = math.atan2( v1.x*v2.y - v1.y*v2.x, v1.dot( v2 ) ) + math.pi
		v1_rotated = mathutils.Vector( ( -v1.y, v1.x ) )
		v3 = ( mathutils.Vector( next_l[uvlayer].uv ) + mathutils.Vector( prev_l[uvlayer].uv ) ) * 0.5
		v3 = ( v3 - mathutils.Vector( l[uvlayer].uv ) ).normalized()
		if v1_rotated.dot( v3 ) < 0.0:
			theta = math.pi * 2.0 - theta

		#bias if no loops between prev_l and next_l
		if prev_l.link_loop_next == l:
			theta *= 0.8

		sorted_tuples.append( ( theta, l ) )
	sorted_tuples = sorted( sorted_tuples, key=lambda x: x[0] )
	return [ p[1] for p in sorted_tuples ][:4]


def clear_tags( rmmesh ):
	for v in rmmesh.bmesh.verts:
		v.tag = False
	for e in rmmesh.bmesh.edges:
		e.tag = False
	for f in rmmesh.bmesh.faces:
		f.tag = False
		for l in f.loops:
			l.tag = False
			
def is_boundary( l ):
	if l.edge.seam or l.edge.is_boundary:
		return True
	else:
		for nf in l.edge.link_faces:
			if nf != l.face and not nf.tag:
				return True
	return False

def GetBoundaryLoops( faces ):
	bounary_loops = set()
	for f in faces:
		for l in f.loops:
			if is_boundary( l ):
				bounary_loops.add( l )
	return bounary_loops

class RelaxVertex():
	all_verts = []

	def __init__( self, vertex, polygon ):
		self._v = vertex
		self._polygons = set( [polygon] )
		self._idx = len( RelaxVertex.all_verts )
		RelaxVertex.all_verts.append( self )

	@classmethod
	def GetRelaxVert( cls, vertex, polygon ):
		for rv in RelaxVertex.all_verts:
			if rv._v == vertex:
				if rv._v.tag:
					#iterate through all polys in nrv to ensure we are not adding a polygon thats on the other side of a seam edge
					for rp in rv._polygons:
						e = shared_edge( rp, polygon )
						if e is None or not e.seam:
							rv._polygons.add( polygon )
							return rv
				else:
					rv._polygons.add( polygon )
					return rv	
		return cls( vertex, polygon )


def shared_edge( p1, p2 ):
	for e in p1.edges:
		for np in e.link_faces:
			if np == p2:
				return e
	return None


def lscm_patches( polygons ):
	#tag epts of seam edges
	for p in polygons:
		for e in p.edges:
			if e.seam:
				v1, v2 = e.verts
				v1.tag = True
				v2.tag = True
			
	for poly in polygons:
		if poly.tag:
			continue
		poly.tag = True
			
		innerSet = []
		outerSet = set( [ poly ] )
		
		while len( outerSet ) > 0:
			p = outerSet.pop()

			rp = [] #relaxpoly which is just a list of relaxverts
			for l in p.loops:
				rv = RelaxVertex.GetRelaxVert( l.vert, p )
				rp.append( rv )

				for nl in l.vert.link_loops:
					np = nl.face
					if np.tag:
						continue
					if l.vert.tag:
						e = shared_edge( p, np )
						if e is None or e.seam:
							continue
					if np in polygons:
						outerSet.add( np )
						np.tag = True

			innerSet.append( rp )
						
		yield innerSet
		RelaxVertex.all_verts.clear()


def DoubleTriangleArea( p1, p2, p3 ):
	return ( p1[0] * p2[1] - p1[1] * p2[0] ) + ( p2[0] * p3[1] - p2[1] * p3[0] ) + ( p3[0] * p1[1] - p3[1] * p1[0] )


def lscm( faces, uvlayer, axisidx ):
	RelaxVertex.all_verts.clear()
	for patch in lscm_patches( faces ):
		#gather input 3dcoords, uvcoords, tri index mappings, and loops
		verts = [ rv._v for rv in RelaxVertex.all_verts ]		
		unique_3d_coords = [ mathutils.Vector( v.co.copy() ) for v in verts ]

		tris = []
		for rlxPoly in patch:
			if len( rlxPoly ) < 3:
				continue
			root_vert = rlxPoly[0]
			for i in range( len( rlxPoly ) - 2 ):
				tris += [ root_vert._idx, rlxPoly[i+1]._idx, rlxPoly[i+2]._idx ]

		all_uv_coords = []
		for rv in RelaxVertex.all_verts:
			for l in rv._v.link_loops:
				if l.face not in rv._polygons:
					continue
				else:
					all_uv_coords.append( mathutils.Vector( l[uvlayer].uv.copy() ) )
					break

		pinned_indexes = []
		pinned_uv_coords = []		
		for i, rv in enumerate( RelaxVertex.all_verts ):
			pinned_loop = False
			for l in rv._v.link_loops:
				if l.face not in rv._polygons:
					continue
				if l[uvlayer].pin_uv:
					pinned_indexes.append( RelaxVertex.all_verts[i]._idx )
					pinned_uv_coords.append( mathutils.Vector( l[uvlayer].uv.copy() ) )
					pinned_loop = True
					break
			

		if len( pinned_indexes ) < 2:
			pinned_indexes.clear()
			pinned_uv_coords.clear()
			pinned_indexes.append( RelaxVertex.all_verts[0]._idx )
			pinned_indexes.append( RelaxVertex.all_verts[-1]._idx )
			pinned_uv_coords.append( mathutils.Vector( RelaxVertex.all_verts[0]._v.link_loops[0][uvlayer].uv.copy() ) )
			pinned_uv_coords.append( mathutils.Vector( RelaxVertex.all_verts[-1]._v.link_loops[0][uvlayer].uv.copy() ) )
			
		#allocate memory for block matrices and pinned vert vector
		tcount = int( len( tris ) / 3 )
		pinned_vcount = len( pinned_indexes )
		vcount = len( verts ) - pinned_vcount
		Mr_f = np.zeros( ( tcount, vcount ) )
		Mi_f = np.zeros( ( tcount, vcount ) )
		Mr_p = np.zeros( ( tcount, pinned_vcount ) )
		Mi_p = np.zeros( ( tcount, pinned_vcount ) )
		b = np.zeros( ( pinned_vcount * 2 ) )

		constrained = np.zeros( ( vcount ) )
		constrain_axis = 1
		
		#compute coefficients
		for i in range( tcount ):
			idx1 = tris[i*3]
			idx2 = tris[i*3+1]
			idx3 = tris[i*3+2]
			
			#project 3d tri to its own plane to get rid of z component
			tri3d = [ unique_3d_coords[idx1], unique_3d_coords[idx2], unique_3d_coords[idx3] ]
			edge_lengths = [ ( tri3d[n-1] - tri3d[n-2] ).length for n in range( 3 ) ]
			theta = math.acos( ( edge_lengths[1] * edge_lengths[1] + edge_lengths[2] * edge_lengths[2] - edge_lengths[0] * edge_lengths[0] ) / ( 2.0 * edge_lengths[1] * edge_lengths[2] ) )                
			proj_tri = []
			proj_tri.append( mathutils.Vector( ( 0.0, 0.0 ) ) )
			proj_tri.append( mathutils.Vector( ( edge_lengths[2], 0.0 ) ) )
			proj_tri.append( mathutils.Vector( ( edge_lengths[1] * math.cos( theta ), edge_lengths[1] * math.sin( theta )  ) ) )
			
			#compute projected tri area
			a = DoubleTriangleArea( proj_tri[0], proj_tri[1], proj_tri[2] )
					
			#compute tris as complex numbers     
			ws = []
			for j in range( 3 ):
				vec = proj_tri[j-1] - proj_tri[j-2]
				ws.append( vec * ( 1.0 / a ) )
				
			#build A (free) and B (pinned) block matrices as well as pinned uv vector ( b )
			for j, vidx in enumerate( [ idx1, idx2, idx3 ] ):
				if vidx in pinned_indexes:
					pvidx = pinned_indexes.index( vidx )
					Mr_p[i][pvidx] = ws[j][0]
					Mi_p[i][pvidx] = ws[j][1]
					
					b[pvidx] = pinned_uv_coords[pvidx][0]
					b[pvidx+pinned_vcount] = pinned_uv_coords[pvidx][1]
				else:
					#adjust for pinned vert indexes
					pin_count = 0
					for pidx in pinned_indexes:
						if vidx > pidx:
							pin_count += 1
					Mr_f[i][vidx-pin_count] = ws[j][0]
					Mi_f[i][vidx-pin_count] = ws[j][1]

					constrained[vidx-pin_count] = all_uv_coords[vidx][constrain_axis]
					
		if constrain_axis == 0:
			bi = b[pinned_vcount:]
			r = Mr_p @ bi
			arxr = Mr_f @ constrained
			x = np.linalg.lstsq( Mi_f, -r + arxr, rcond=None )[0]

		elif constrain_axis == 1:
			br = b[:pinned_vcount]
			r = Mr_p @ br
			aixi = Mi_f @ constrained
			x = np.linalg.lstsq( Mr_f, r + aixi, rcond=None )[0]

		else:
			A = np.block( [
				[ Mr_f, Mi_f * -1.0 ],
				[ Mi_f, Mr_f ] ] )
				
			B = np.block( [
				[ Mr_p, Mi_p * -1.0 ],
				[ Mi_p, Mr_p ] ] )
			
			#compute r = -(B * b)
			r = B @ b
			r = r * -1.0
			
			#solve for x inf Ax=b
			x = np.linalg.lstsq( A, r, rcond=None )[0]

		#assign new uv values
		for vidx, v in enumerate( verts ):
			count = 0
			for pidx in pinned_indexes:
				if vidx > pidx:
					count += 1
			if vidx in pinned_indexes:
				continue
			for l in verts[vidx].link_loops:
				if l.face in RelaxVertex.all_verts[vidx]._polygons:
					if constrain_axis == 0:
						l[uvlayer].uv[1] = x[vidx-count]
					elif constrain_axis == 1:
						l[uvlayer].uv[0] = x[vidx-count]
					else:
						l[uvlayer].uv = mathutils.Vector( ( x[vidx-count], x[(vidx-count+vcount)] ) )

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


class MESH_OT_uvrectangularize( bpy.types.Operator ):
	"""Map the selection to a box."""
	bl_idname = 'mesh.rm_uvrectangularize'
	bl_label = 'Rectangularize'
	bl_options = { 'UNDO' }

	@classmethod
	def poll( cls, context ):
		return ( ( context.area.type == 'VIEW_3D' or context.area.type == 'IMAGE_EDITOR' ) and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):
		rmmesh = rmlib.rmMesh.GetActive( context )
		if rmmesh is None:
			return { 'CANCELLED' }
			
		with rmmesh as rmmesh:
			uvlayer = rmmesh.active_uv
			clear_tags( rmmesh )

			#get selection of faces
			faces = rmlib.rmPolygonSet()
			groups = []
			override_corners = []
			sel_sync = context.tool_settings.use_uv_select_sync
			sel_mode = context.tool_settings.mesh_select_mode[:]
			uv_sel_mode = context.tool_settings.uv_select_mode
			if sel_sync or context.area.type == 'VIEW_3D':				
				if sel_mode[2]:
					faces = rmlib.rmPolygonSet.from_selection( rmmesh )
					groups = faces.group( use_seam=True )
				else:
					self.report( { 'ERROR' }, 'Must be in face mode.' )
					return { 'CANCELLED' }
			else:
				if uv_sel_mode == 'VERTEX':
					loop_selection = rmlib.rmUVLoopSet.from_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					override_corners = loop_selection.border_loops()
					if len( override_corners ) != 4:
						self.report( { 'ERROR' }, 'Must have exactly 4 uvverts selected. All must be on the boundary of the same uvisland.' )
						return { 'CANCELLED' }
					vertgroups = loop_selection.group_vertices( element=True )
					if len( vertgroups ) != 1:
						self.report( { 'ERROR' }, 'Corner uvverts must all be members of the same uvisland.' )
						return { 'CANCELLED' }
					visible_faces = GetUnsyncUVVisibleFaces( rmmesh, sel_mode )
					for l in vertgroups[0]:
						if l.face in visible_faces and l.face not in faces:
							faces.append( l.face )
					groups = [faces]
				elif uv_sel_mode == 'FACE':
					visible_faces = GetUnsyncUVVisibleFaces( rmmesh, sel_mode )
					loop_selection = rmlib.rmUVLoopSet.from_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					for l in loop_selection:
						if l.face in visible_faces and l.face not in faces:
							faces.append( l.face )
					groups = faces.group( use_seam=True )
				else:
					self.report( { 'ERROR' }, 'Must be in uvvert or uvface mode.' )
					return { 'CANCELLED' }

			if len( faces ) < 1:
				self.report({'ERROR'}, 'Could not find more than one face to operate on!!!' )
				return { 'CANCELLED' }
			
			#clear loop selection
			if sel_sync or context.area.type == 'VIEW_3D':
				for f in faces:
					f.select = False
			else:
				for f in rmmesh.bmesh.faces:
					for l in f.loops:
						l[uvlayer].select = False
						l[uvlayer].select_edge = False

			for group in groups:
				clear_tags( rmmesh )

				#tag faces in group
				if sel_sync or context.area.type == 'VIEW_3D':
					for f in group:
						f.tag = True
						f.select = True
				else:
					for f in group:
						f.tag = True
						for l in f.loops:
							l[uvlayer].select = True
							l[uvlayer].select_edge = True
					
				#get list of boundary loops
				bounary_loops = GetBoundaryLoops( group )
				if len( bounary_loops ) < 4:
						continue
				
				#unpin boundary loops so they dont interfere and store initial bbox
				initial_uvcoords = []
				for f in group:
					for l in f.loops:
						l[uvlayer].pin_uv = False
						initial_uvcoords.append( l[uvlayer].uv.copy() )
				initial_bbmin, initial_bbmax = BBoxFromPoints( initial_uvcoords )

				#if there are exactly two boundary_loop_groups then we assume the shape a cylinder and
				#we need to add seam edges to map it to a plane.
				boundary_edge_groups = rmlib.rmEdgeSet( [ l.edge for l in bounary_loops ] ).chain()
				if ( len( boundary_edge_groups ) == 2 and
				boundary_edge_groups[0][0][0] == boundary_edge_groups[0][-1][-1] and
				boundary_edge_groups[-1][0][0] == boundary_edge_groups[-1][-1][-1] and
				len( override_corners ) != 4 ):
					starting_vert = boundary_edge_groups[0][0][0]
					end_verts = [ pair[0] for pair in boundary_edge_groups[-1] ]
					all_verts = group.vertices
					path_verts = shortest_path( starting_vert, end_verts, all_verts )
					for i in range( 1, len( path_verts ) ):
						e = rmlib.rmEdgeSet.from_endpoints( path_verts[i-1], path_verts[i] )
						e.seam = True
					bounary_loops = GetBoundaryLoops( group )
					if len( bounary_loops ) < 4:
							continue
				elif len( override_corners ) == 4:
					for l in rmlib.rmUVLoopSet( faces.loops, uvlayer=uvlayer ).border_loops():
						l.edge.seam = True
					bounary_loops = GetBoundaryLoops( group )
					if len( bounary_loops ) < 4:
							continue
				sorted_boundary_loops = sort_loop_chain( rmlib.rmUVLoopSet( bounary_loops, uvlayer=uvlayer ) )
				
				#lscm - initial conformal map to find four corners
				#clear_tags( rmmesh )
				pinned_loops = set()
				for l in sorted_boundary_loops[0].vert.link_loops:
					l[uvlayer].pin_uv = True
					pinned_loops.add( l )
				middle_idx = int( len( sorted_boundary_loops ) / 2.0 )
				for l in sorted_boundary_loops[middle_idx].vert.link_loops:
					l[uvlayer].pin_uv = True
					pinned_loops.add( l )			
				sorted_boundary_loops[middle_idx][uvlayer].pin_uv = True
				bpy.ops.uv.unwrap(method="CONFORMAL")
				#lscm( faces, uvlayer )
				#clear_tags( rmmesh )
				for l in pinned_loops:
					l[uvlayer].pin_uv = False
				sorted_boundary_loops[0][uvlayer].pin_uv = False
				sorted_boundary_loops[middle_idx][uvlayer].pin_uv = False

				#re-tag face tags
				clear_tags( rmmesh )
				for f in group:
					f.tag = True

				corner_loops = []
				if len( override_corners ) == 4:
					corner_loops = override_corners
				else:
					corner_loops = GetPinCornersByAngle( sorted_boundary_loops, uvlayer )

				#compute the distance between the corners
				lcount = len( sorted_boundary_loops )
				distance_between_corners = []
				edge_distances = [ 0.0 ] * lcount
				starting_idx = sorted_boundary_loops.index( corner_loops[0] )
				for i in range( lcount ):
					idx = ( starting_idx + i ) % lcount
					l = sorted_boundary_loops[idx]
					if l in corner_loops:
						distance_between_corners.append( 0.0 )
					v1, v2 = l.edge.verts
					d = ( mathutils.Vector( v1.co ) - mathutils.Vector( v2.co ) ).length
					edge_distances[idx] = d
					distance_between_corners[-1] += d

				dir_lookup = [ mathutils.Vector( ( 1.0, 0.0 ) ), mathutils.Vector( ( 0.0, 1.0 ) ), mathutils.Vector( ( -1.0, 0.0 ) ), mathutils.Vector( ( 0.0, -1.0 ) ) ]
				max_len = -1.0
				for i in range( 2, 4 ):
					dir_lookup[i] = dir_lookup[i] * ( distance_between_corners[i-2] / distance_between_corners[i] )
				for i in range( 4 ):
					max_len = max( max_len, distance_between_corners[i] )
				for i in range( 4 ):
					dir_lookup[i] *= 1.0 / max_len

				#set and pin loops to said corners
				only_pin_corners = False
				origin = mathutils.Vector( ( 0.0, 0.0 ) )
				pinned_loops = set()
				corner_count = -1
				for i in range( lcount ):
					idx = ( starting_idx + i ) % lcount
					l = sorted_boundary_loops[idx]
					
					origin += dir_lookup[corner_count] * edge_distances[idx-1]

					if l in corner_loops:
						corner_count += 1
					else:
						if only_pin_corners:
							continue

					pls = prev_boundary_loop( l )
					for nl in pls:
						nl = nl.link_loop_next
						nl[uvlayer].uv = origin
						nl[uvlayer].pin_uv = True
						pinned_loops.add( nl )
					
				#lscm
				#clear_tags( rmmesh )
				#lscm( faces, uvlayer )
				bpy.ops.uv.unwrap( method='CONFORMAL' )
				clear_tags( rmmesh )

				if context.area.type != 'VIEW_3D':
					FitToBBox( faces, initial_bbmin, initial_bbmax, uvlayer )
	
				#clear pins
				for l in pinned_loops:
					l[uvlayer].pin_uv = False

				#unscale island horizontally
				if sel_sync and sel_mode[0]:
					context.tool_settings.mesh_select_mode = ( False, False, True )
				elif not sel_sync and uv_sel_mode == 'VERTEX':
					context.tool_settings.uv_select_mode = 'FACE'
				bpy.ops.mesh.rm_normalizetexels( uv_map_name=uvlayer.name, horizontal=True )
				if sel_sync and sel_mode[0]:
					context.tool_settings.mesh_select_mode = ( sel_mode[0], False, False )
				elif not sel_sync and uv_sel_mode == 'VERTEX':
					context.tool_settings.uv_select_mode = 'VERTEX'

				#clear loop selection
				if sel_sync or context.area.type == 'VIEW_3D':
					for f in group:
						f.select = False
				else:
					for f in group:
						for l in f.loops:
							l[uvlayer].select = False
							l[uvlayer].select_edge = False

			#restore initial loop selection
			if sel_sync or context.area.type == 'VIEW_3D':
				faces.select()
			else:
				for l in loop_selection:
					l[uvlayer].select = True
					if len( override_corners ) != 4:
						l[uvlayer].select_edge = True

		return { 'FINISHED' }
	

class MESH_OT_lscm( bpy.types.Operator ):
	"""Map the selection to a box."""
	bl_idname = 'mesh.rm_lscm'
	bl_label = 'LSCM'
	bl_options = { 'UNDO' }

	@classmethod
	def poll( cls, context ):
		return ( ( context.area.type == 'VIEW_3D' or context.area.type == 'IMAGE_EDITOR' ) and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):
		rmmesh = rmlib.rmMesh.GetActive( context )
		if rmmesh is None:
			return { 'CANCELLED' }
			
		with rmmesh as rmmesh:
			uvlayer = rmmesh.active_uv
			clear_tags( rmmesh )

			#get selection of faces
			faces = rmlib.rmPolygonSet()
			groups = []
			override_corners = []
			sel_sync = context.tool_settings.use_uv_select_sync
			sel_mode = context.tool_settings.mesh_select_mode[:]
			uv_sel_mode = context.tool_settings.uv_select_mode
			if sel_sync or context.area.type == 'VIEW_3D':				
				if sel_mode[2]:
					faces = rmlib.rmPolygonSet.from_selection( rmmesh )
					groups = faces.group( use_seam=True )
				else:
					self.report( { 'ERROR' }, 'Must be in face mode.' )
					return { 'CANCELLED' }
			else:
				if uv_sel_mode == 'VERTEX':
					loop_selection = rmlib.rmUVLoopSet.from_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					override_corners = loop_selection.border_loops()
					if len( override_corners ) != 4:
						self.report( { 'ERROR' }, 'Must have exactly 4 uvverts selected. All must be on the boundary of the same uvisland.' )
						return { 'CANCELLED' }
					vertgroups = loop_selection.group_vertices( element=True )
					if len( vertgroups ) != 1:
						self.report( { 'ERROR' }, 'Corner uvverts must all be members of the same uvisland.' )
						return { 'CANCELLED' }
					visible_faces = GetUnsyncUVVisibleFaces( rmmesh, sel_mode )
					for l in vertgroups[0]:
						if l.face in visible_faces and l.face not in faces:
							faces.append( l.face )
					groups = [faces]
				elif uv_sel_mode == 'FACE':
					visible_faces = GetUnsyncUVVisibleFaces( rmmesh, sel_mode )
					loop_selection = rmlib.rmUVLoopSet.from_selection( rmmesh=rmmesh, uvlayer=uvlayer )
					for l in loop_selection:
						if l.face in visible_faces and l.face not in faces:
							faces.append( l.face )
					groups = faces.group( use_seam=True )
				else:
					self.report( { 'ERROR' }, 'Must be in uvvert or uvface mode.' )
					return { 'CANCELLED' }

			if len( faces ) < 1:
				self.report({'ERROR'}, 'Could not find more than one face to operate on!!!' )
				return { 'CANCELLED' }
			
			#clear loop selection
			if sel_sync or context.area.type == 'VIEW_3D':
				for f in faces:
					f.select = False
			else:
				for f in rmmesh.bmesh.faces:
					for l in f.loops:
						l[uvlayer].select = False
						l[uvlayer].select_edge = False

			for group in groups:
				clear_tags( rmmesh )
				
				#unpin boundary loops so they dont interfere and store initial bbox
				initial_uvcoords = []
				for f in group:
					for l in f.loops:
						initial_uvcoords.append( l[uvlayer].uv.copy() )
				initial_bbmin, initial_bbmax = BBoxFromPoints( initial_uvcoords )

				lscm( group, uvlayer, 2 )

				#if context.area.type == 'VIEW_3D':
				#	FitToBBox( group, mathutils.Vector( ( 0.0, 0.0 ) ), mathutils.Vector( ( 1.0, 1.0 ) ), uvlayer, True )
				#else:
				#	FitToBBox( group, initial_bbmin, initial_bbmax, uvlayer, True )

			clear_tags( rmmesh )

		return { 'FINISHED' }


def register():
	bpy.utils.register_class( MESH_OT_uvrectangularize )
	bpy.utils.register_class( MESH_OT_lscm )

def unregister():
	bpy.utils.unregister_class( MESH_OT_uvrectangularize )
	bpy.utils.unregister_class( MESH_OT_lscm )