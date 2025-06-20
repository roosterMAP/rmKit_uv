import rmlib
import bpy, bmesh, mathutils
import os, random, math, struct, ctypes

MAT_CHUNK = 'MAT'
HOT_CHUNK = 'HOT'

MAX_SHORT = 1 << 15

def clear_tags( rmmesh ):
	for v in rmmesh.bmesh.verts:
		v.tag = False
	for e in rmmesh.bmesh.edges:
		e.tag = False
	for f in rmmesh.bmesh.faces:
		f.tag = False
		for l in f.loops:
			l.tag = False


def GetFaceSelection( context, rmmesh ):
	uvlayer = rmmesh.active_uv
	clear_tags( rmmesh )

	faces = rmlib.rmPolygonSet()
	sel_sync = context.tool_settings.use_uv_select_sync
	if sel_sync or context.area.type == 'VIEW_3D':
		sel_mode = context.tool_settings.mesh_select_mode[:]
		if sel_mode[2]:
			faces = rmlib.rmPolygonSet.from_selection( rmmesh )
		else:
			return faces
	else:
		sel_mode = context.tool_settings.uv_select_mode
		loops = rmlib.rmUVLoopSet.from_selection( rmmesh, uvlayer=uvlayer )
		loop_faces = set()
		for l in loops:
			if not l.face.select and sel_mode != 'EDGE':
				continue
			if not l[uvlayer].select_edge and sel_mode != 'VERT':
				continue
			loop_faces.add( l.face )
			l.tag = True
		for f in loop_faces:
			all_loops_tagged = True
			for l in f.loops:
				if not l.tag:
					all_loops_tagged = False
				else:
					l.tag = False
			if all_loops_tagged:
				faces.append( f )

	clear_tags( rmmesh )

	return faces


def load_mat_subchunk( chunk, offset ):
	'''
	#Chunk layout described below:
	3s(chunkname)
	I(groupcount)
		I(strcount for group)
			I(charcount fror string)
			{}s.format(charcount)(string)
			...
		...
	'''
	chunk_name = struct.unpack_from( '>3s', chunk, offset )[0].decode( 'utf-8' )
	if chunk_name != MAT_CHUNK:
		raise RuntimeError
	offset += 3
	str_list = []
	group_count = struct.unpack_from( '>I', chunk, offset )[0]
	offset += 4
	str_groups = []
	for i in range( group_count ):
		str_count = struct.unpack_from( '>I', chunk, offset )[0]
		offset += 4
		str_list = []
		for j in range( str_count ):
			size = struct.unpack_from( '>I', chunk, offset )[0]
			offset += 4
			s = struct.unpack_from( '>{}s'.format( size ), chunk, offset )[0].decode( 'utf-8' )
			str_list.append( s )
			offset += size
		str_groups.append( str_list )
	return str_groups, offset


def load_hot_chunk( chunk, offset ):
	'''
	#Chunk layout described below:
	3s(chunkname)
	I(hotspotcount)
		hotspot data
		...
	'''
	chunk_name = struct.unpack_from( '>3s', chunk, offset )[0].decode( 'utf-8' )
	if chunk_name != HOT_CHUNK:
		raise RuntimeError
	offset += 3
	hotspots = []
	hotspot_count = struct.unpack_from( '>I', chunk, offset )[0]
	offset += 4
	for i in range( hotspot_count ):
		new_hotspot, offset = Hotspot.unpack( chunk, offset )
		hotspots.append( new_hotspot )
	return hotspots, offset


class Bounds2d():
	def __init__( self, points, **kwargs ):
		self.__min = mathutils.Vector( ( 0.0, 0.0 ) )
		self.__max = mathutils.Vector( ( 1.0, 1.0 ) )
		self.__materialaspect = 1.0
		self.__horizontal = self.__max[0] - self.__min[0] > self.__max[1] - self.__min[1]
		if len( points ) > 0:
			self.__min = points[0].copy()
			self.__max = points[0].copy()
		#self.__inset = mathutils.Vector( ( 0.0, 0.0 ) )
		#self.__properties = {}
		for p in points:
			for i in range( 2 ):
				self.__min[i] = min( p[i], self.__min[i] )
				self.__max[i] = max( p[i], self.__max[i] )

		for key, value in kwargs.items():
			if key == 'materialaspect':
				self.__materialaspect = value
				self.__horizontal = ( self.__max[0] - self.__min[0] ) * self.__materialaspect > self.__max[1] - self.__min[1]

	def __repr__( self ):
		return 'min:Vec2( {}, {} )  max:Vec2( {}, {} )'.format( self.__min[0], self.__min[1], self.__max[0], self.max[1] )

	def __eq__( self, __o ):
		return rmlib.util.AlmostEqual_v2( self.__min, __o.__min ) and rmlib.util.AlmostEqual_v2( self.__max, __o.__max )

	def __bytes__( self ):
		return struct.pack( '>HHHH', ctypes.c_ushort( int( self.__min[0] * MAX_SHORT ) ).value,
									ctypes.c_ushort( int( self.__min[1] * MAX_SHORT ) ).value,
									ctypes.c_ushort( int( self.__max[0] * MAX_SHORT ) ).value,
									ctypes.c_ushort( int( self.__max[1] * MAX_SHORT ) ).value )

	@classmethod
	def from_verts( cls, verts, **kwargs ):
		#build bounds from list of BMVerts
		poslist = [ v.co.to_2d() for v in verts ]
		return cls( poslist, **kwargs )

	@classmethod
	def from_loops( cls, loops, uvlayer, **kwargs ):
		#build bounds from list of BMVerts
		uvlist = [ l[uvlayer].uv.copy() for l in loops ]
		return cls( uvlist, **kwargs )

	@property
	def min( self ):
		return self.__min

	@property
	def max( self ):
		return self.__max

	@property
	def width( self ):
		return self.__max[0] - self.__min[0]

	@property
	def height( self ):
		return self.__max[1] - self.__min[1]

	@property
	def aspect( self ):
		return self.width * self.__materialaspect / self.height
	
	@property
	def invaspect( self ):
		return self.height / ( self.width * self.__materialaspect )
	
	@property
	def area( self ):
		return self.width * self.height

	@property
	def center( self ):
		return ( self.__min + self.__max ) * 0.5

	@property
	def horizontal( self ):
		#returns true if self is wider than it is tall
		return self.__horizontal

	@property
	def tiling( self ):
		if self.__max[0] - self.__min[0] == 1.0:
			return 1
		if self.__max[1] - self.__min[1] == 1.0:
			return 2
		return 0

	@property
	def corners( self ):
		#return corner coords of self in (u,v) domain
		return [ self.__min, mathutils.Vector( ( self.__max[0], self.__min[1] ) ), self.__max, mathutils.Vector( ( self.__min[0], self.__max[1] ) ) ]
	
	@property
	def materialaspect( self ):
		return self.__materialaspect
	
	@materialaspect.setter
	def materialaspect( self, value ):
		self.__materialaspect = value
		self.__horizontal = self.width * self.__materialaspect > self.height

	def clamp( self ):
		new_bounds = Bounds2d( [ self.__min, self.__max ] )

		#move into unit square
		center = ( new_bounds.__min + new_bounds.__max ) / 2.0
		center.x = math.floor( center.x )
		center.y = math.floor( center.y )
		new_bounds.__min -= center
		new_bounds.__max -= center

		#clamp to 0.0-1.0 range
		new_bounds.__min.x = max( new_bounds.__min.x, 0.0 )
		new_bounds.__min.y = max( new_bounds.__min.y, 0.0 )
		new_bounds.__max.x = min( new_bounds.__max.x, 1.0 )
		new_bounds.__max.y = min( new_bounds.__max.y, 1.0 )

		return new_bounds

	def normalized( self ):
		#ensure bounds overlapps the 0-1 region
		center = self.center
		new_bounds = Bounds2d( [ self.__min, self.__max ] )
		new_bounds.__min[0] -= float( math.floor( center[0] ) )
		new_bounds.__min[1] -= float( math.floor( center[1] ) )
		new_bounds.__max[0] -= float( math.floor( center[0] ) )
		new_bounds.__max[1] -= float( math.floor( center[1] ) )
		return new_bounds

	def inside( self, point ):
		#test if point is inside self
		return ( point[0] > self.min[0] and point[1] > self.min[1] and point[0] < self.max[0] and point[1] < self.max[1] )

	def overlapping( self, bounds ):
		#test if bounds overlapps self
		return not ( self.__max[0] < bounds.__min[0] or self.__min[0] > bounds.max[0] or self.__max[1] < bounds.__min[1] or self.__min[1] > bounds.max[1] )
	
	def overlapping_area( self, bounds ):
		#does not test if bounds actually overlapp
		min_x = max( self.__min[0], bounds.min[0] )
		min_y = max( self.__min[1], bounds.min[1] )
		max_x = min( self.__max[0], bounds.max[0] )
		max_y = min( self.__max[1], bounds.max[1] )
		return ( max_x - min_x ) * ( max_y - min_y )

	def transform( self, other, skip_rot=False, trim=False, inset=0.0, random_rot=False, random_flip=False ):
		#compute the 3x3 matrix that transforms bound 'other' to self

		if self.width < rmlib.util.FLOAT_EPSILON or self.height < rmlib.util.FLOAT_EPSILON:
			return mathutils.Matrix.Identity( 3 )

		trans_mat = mathutils.Matrix.Identity( 3 )
		trans_mat[0][2] = self.center[0] * -1.0
		trans_mat[1][2] = self.center[1] * -1.0
		
		trans_mat_inverse = mathutils.Matrix.Identity( 3 )
		trans_mat_inverse[0][2] = other.center[0]
		trans_mat_inverse[1][2] = other.center[1]

		other_inset_width = other.width - inset
		other_inset_height = other.height - inset * self.__materialaspect

		#randomly rotate 180 degrees
		rand_rot_mat = mathutils.Matrix.Identity( 3 )
		if random_rot and random.random() > 0.5:
			rand_rot_mat[0][0] = math.cos( math.pi )
			rand_rot_mat[1][0] = math.sin( math.pi ) * -1.0
			rand_rot_mat[0][1] = math.sin( math.pi )
			rand_rot_mat[1][1] = math.cos( math.pi )

		rot_mat = mathutils.Matrix.Identity( 3 )
		scl_mat = mathutils.Matrix.Identity( 3 )
		if trim and ( other.width >= 1.0 or other.height >= 1.0 ):
			if self.horizontal != other.horizontal and not skip_rot:
				rot_mat[0][0] = math.cos( math.pi / 2.0 )
				rot_mat[1][0] = math.sin( math.pi / 2.0 ) * -1.0
				rot_mat[0][1] = math.sin( math.pi / 2.0 )
				rot_mat[1][1] = math.cos( math.pi / 2.0 )

				if other.width >= 1.0:
					scl_mat[1][1] *= other_inset_height / self.width
					scl_mat[0][0] *= other_inset_height / self.width / ( self.__materialaspect * self.__materialaspect )
				else:
					scl_mat[0][0] *= other_inset_width / self.height / ( self.__materialaspect * self.__materialaspect )
					scl_mat[1][1] *= other_inset_width / self.height
			else:
				if other.width >= 1.0:
					scl_mat[1][1] = other_inset_height / self.height
					scl_mat[0][0] = other_inset_height / self.height
				else:
					scl_mat[0][0] = other_inset_width / self.width
					scl_mat[1][1] = other_inset_width / self.width
		else:
			if self.horizontal != other.horizontal and not skip_rot:
				rot_mat[0][0] = math.cos( math.pi / 2.0 )
				rot_mat[1][0] = math.sin( math.pi / 2.0 ) * -1.0
				rot_mat[0][1] = math.sin( math.pi / 2.0 )
				rot_mat[1][1] = math.cos( math.pi / 2.0 )
				scl_mat[0][0] = other_inset_width / self.height
				scl_mat[1][1] = other_inset_height / self.width
			else:
				scl_mat[0][0] = other_inset_width / self.width
				scl_mat[1][1] = other_inset_height / self.height

		#randomly flip along each axis
		if random_flip and random.random() > 0.5:
			scl_mat[0][0] *= -1.0
		if random_flip and random.random() > 0.5:
			scl_mat[1][1] *= -1.0

		return trans_mat_inverse @ scl_mat @ rand_rot_mat @ rot_mat @ trans_mat
	
	def copy( self ):
		return Bounds2d( [ self.__min, self.__max ], materialaspect=self.__materialaspect )

	def inset( self, f, aspect=1.0 ):
		self.__min[0] += f * aspect
		self.__min[1] += f
		self.__max[0] -= f * aspect
		self.__max[1] -= f


class Hotspot():
	def __init__( self, bounds2d_list, **kwargs ):
		self.__name = ''
		self.__properties = None
		self.__data = []
		for b in bounds2d_list:
			if b.area > 0.0:
				self.__data.append( b )
		for key, value in kwargs.items():
			if key == 'name':
				self.__name = value
			elif key == 'properties':
				self.__properties = None

	def __repr__( self ):
		s = 'HOTSPOT :: \"{}\" \n'.format( self.__name )
		#s += '\tproperties :: {}\n'.format( self.__properties )
		for i, r in enumerate( self.__data ):
			s += '\t{} :: {}\n'.format( i, r )
		return s

	def __eq__( self, __o ):
		if len( self.__data ) != len( __o.__data ):
			return False
		
		for b in self.__data:
			if b not in __o.__data:
				return False
			
		return True

	def __bytes__( self ):
		bounds_data = struct.pack( '>I', len( self.__data ) )
		for b in self.__data:
			bounds_data += bytes( b )		
		return bounds_data
	
	@property
	def data( self ):
		return self.__data

	@staticmethod
	def unpack( bytearray, offset ):
		bounds_count = struct.unpack_from( '>I', bytearray, offset )[0]
		offset += 4
		data = []
		for i in range( bounds_count ):
			bmin_x, bmin_y, bmax_x, bmax_y = struct.unpack_from( '>HHHH', bytearray, offset )
			min_pos = mathutils.Vector( ( bmin_x / MAX_SHORT, bmin_y / MAX_SHORT ) )
			max_pos = mathutils.Vector( ( bmax_x / MAX_SHORT, bmax_y / MAX_SHORT ) )
			data.append( Bounds2d( [ min_pos, max_pos ] ) )
			offset += 8
		return Hotspot( data ), offset

	@classmethod
	def from_bmesh( cls, rmmesh ):
		#load hotspot from subrect_atlas		
		boundslist = []
		with rmmesh as rmmesh:
			rmmesh.readonly = True
			uv_layer = rmmesh.bmesh.loops.layers.uv.verify()
			for f in rmmesh.bmesh.faces:
				boundslist.append( Bounds2d.from_loops( f.loops, uv_layer ) )
		return cls( boundslist )

	@property
	def name( self ):
		return self.__name
	
	@property
	def materialaspect( self ):
		return self.__data[0].materialaspect

	def save_bmesh( self, rmmesh ):
		with rmmesh as rmmesh:
			uvlayer = rmmesh.active_uv
			del_faces = list( rmmesh.bmesh.faces )
			
			for bounds in self.__data:
				verts = []
				corners = bounds.corners
				for c in corners:
					verts.append( rmmesh.bmesh.verts.new( c.to_3d() ) )
				f = rmmesh.bmesh.faces.new( verts )
				for i, l in enumerate( f.loops ):
					l[uvlayer].uv = corners[i]

			bmesh.ops.delete( rmmesh.bmesh, geom=del_faces, context='FACES' )

	def match( self, source_bounds, tollerance=0.01, random_orient=True, trim_filter='none' ):
		#find the bound in this hotspot that best matches source
		sb_aspect = min( source_bounds.aspect, source_bounds.invaspect )
		source_coord = mathutils.Vector( ( math.sqrt( source_bounds.area ), sb_aspect ) )

		min_dist = 9999999.9
		best_bounds = self.__data[0]
		for tb in self.__data:
			if trim_filter == 'onlytrim':
				if tb.width < 1.0 or tb.height < 1.0:
					continue

			elif trim_filter == 'notrim':
				if tb.width >= 1.0 or tb.height >= 1.0:
					continue

			if not random_orient and tb.horizontal != best_bounds.horizontal:
				continue

			aspect = min( tb.aspect, tb.invaspect )
			target_coord = mathutils.Vector( ( math.sqrt( tb.area ), aspect ) )
			dist = ( target_coord - source_coord ).length
			if dist < min_dist:
				min_dist = dist
				best_bounds = tb
		best_aspect = min( best_bounds.aspect, best_bounds.invaspect )
		best_coord = mathutils.Vector( ( math.sqrt( best_bounds.area ), best_aspect ) )

		target_list = []
		for tb in self.__data:
			aspect = min( tb.aspect, tb.invaspect )
			target_coord = mathutils.Vector( ( math.sqrt( tb.area ), aspect ) )
			if ( target_coord - best_coord ).length <= tollerance:			
				if not random_orient and tb.horizontal == best_bounds.horizontal:
						target_list.append( tb )
				else:
					target_list.append( tb )

		if len( target_list ) == 0:
			return None

		return random.choice( target_list )

	def nearest( self, u, v ):
		#normalize u and v
		u -= math.floor( u )
		v -= math.floor( v )

		#find the bounds nearest to (u,v) coord
		point = mathutils.Vector( ( u, v ) )
		nearest_rect = self.__data[0]
		nearest_rect_dist = 999999999.9
		for b in self.__data:
			if b.inside( point ):
				return b
			min_dist = 999999999.9
			for c in b.corners:
				dist = ( c - point ).length
				if dist < min_dist:
					min_dist = dist
			if min_dist < nearest_rect_dist:
				nearest_rect_dist = min_dist
				nearest_rect = b

		return nearest_rect

	def overlapping( self, bounds2d ):
		b_in = bounds2d.normalized()

		#find the bounds that most overlapps bounds2d
		max_overlap_area = -1.0
		overlap_bounds = self.__data[0]
		for b in self.__data:
			if b.overlapping( b_in ):
				overlap_area = b.overlapping_area( b_in )
				if overlap_area > max_overlap_area:
					max_overlap_area = overlap_area
					overlap_bounds = b
		return overlap_bounds
	
	def applymaterialaspect( self, material_aspect ):
		for b in self.__data:
			b.materialaspect = material_aspect


def write_default_file( file ):
	bounds = []
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.5, 0.0 ) ), mathutils.Vector( ( 0.75, 0.5 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.9375, 0.0 ) ), mathutils.Vector( ( 0.96875, 0.5 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.75, 0.0 ) ), mathutils.Vector( ( 0.875, 0.5 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.0, 0.0 ) ), mathutils.Vector( ( 0.5, 0.5 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.875, 0.0 ) ), mathutils.Vector( ( 0.9375, 0.5 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.75, 0.5 ) ), mathutils.Vector( ( 0.875, 0.75 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.875, 0.5 ) ), mathutils.Vector( ( 0.9375, 0.75 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.0, 0.5 ) ), mathutils.Vector( ( 0.5, 0.75 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.5, 0.5 ) ), mathutils.Vector( ( 0.75, 0.75 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.9375, 0.5 ) ), mathutils.Vector( ( 0.96875, 0.75 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.875, 0.75 ) ), mathutils.Vector( ( 0.9375, 0.875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.5, 0.75 ) ), mathutils.Vector( ( 0.75, 0.875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.9375, 0.75 ) ), mathutils.Vector( ( 0.96875, 0.875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.75, 0.75 ) ), mathutils.Vector( ( 0.875, 0.875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.0, 0.75 ) ), mathutils.Vector( ( 0.5, 0.875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.0, 0.875 ) ), mathutils.Vector( ( 0.5, 0.9375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.5, 0.875 ) ), mathutils.Vector( ( 0.75, 0.9375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.9375, 0.875 ) ), mathutils.Vector( ( 0.96875, 0.9375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.875, 0.875 ) ), mathutils.Vector( ( 0.9375, 0.9375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.75, 0.875 ) ), mathutils.Vector( ( 0.875, 0.9375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.875, 0.9375 ) ), mathutils.Vector( ( 0.9375, 0.96875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.9375, 0.9375 ) ), mathutils.Vector( ( 0.96875, 0.96875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.75, 0.9375 ) ), mathutils.Vector( ( 0.875, 0.96875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.0, 0.9375 ) ), mathutils.Vector( ( 0.5, 0.96875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.5, 0.9375 ) ), mathutils.Vector( ( 0.75, 0.96875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.984375, 0.9375 ) ), mathutils.Vector( ( 1.0, 0.96875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.96875, 0.9375 ) ), mathutils.Vector( ( 0.984375, 0.96875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.984375, 0.875 ) ), mathutils.Vector( ( 1.0, 0.9375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.96875, 0.875 ) ), mathutils.Vector( ( 0.984375, 0.9375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.984375, 0.75 ) ), mathutils.Vector( ( 1.0, 0.875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.96875, 0.75 ) ), mathutils.Vector( ( 0.984375, 0.875 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.984375, 0.0 ) ), mathutils.Vector( ( 1.0, 0.5 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.96875, 0.0 ) ), mathutils.Vector( ( 0.984375, 0.5 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.984375, 0.5 ) ), mathutils.Vector( ( 1.0, 0.75 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.96875, 0.5 ) ), mathutils.Vector( ( 0.984375, 0.75 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.0, 0.984375 ) ), mathutils.Vector( ( 0.5, 1.0 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.0, 0.96875 ) ), mathutils.Vector( ( 0.5, 0.984375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.96875, 0.96875 ) ), mathutils.Vector( ( 0.984375, 0.984375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.96875, 0.984375 ) ), mathutils.Vector( ( 0.984375, 1.0 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.9375, 0.984375 ) ), mathutils.Vector( ( 0.96875, 1.0 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.9375, 0.96875 ) ), mathutils.Vector( ( 0.96875, 0.984375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.984375, 0.984375 ) ), mathutils.Vector( ( 1.0, 1.0 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.984375, 0.96875 ) ), mathutils.Vector( ( 1.0, 0.984375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.5, 0.984375 ) ), mathutils.Vector( ( 0.75, 1.0 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.5, 0.96875 ) ), mathutils.Vector( ( 0.75, 0.984375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.75, 0.984375 ) ), mathutils.Vector( ( 0.875, 1.0 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.75, 0.96875 ) ), mathutils.Vector( ( 0.875, 0.984375 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.875, 0.984375 ) ), mathutils.Vector( ( 0.9375, 1.0 ) ) ] ) )
	bounds.append( Bounds2d( [ mathutils.Vector( ( 0.875, 0.96875 ) ), mathutils.Vector( ( 0.9375, 0.984375 ) ) ] ) )
	hotspot = Hotspot( bounds, name='default' )

	with open( file, 'wb' ) as f:
		#write material chunk
		f.write( struct.pack( '>3s', bytes( MAT_CHUNK, 'utf-8' ) ) )
		f.write( struct.pack( '>I', 1 ) )
		for matgroup in [ [ 'default' ] ]:
			f.write( struct.pack( '>I', len( matgroup ) ) )
			for mat in matgroup:
				size = len( mat )
				f.write( struct.pack( '>I', size ) )
				f.write( struct.pack( '>{}s'.format( size ), bytes( mat, 'utf-8' ) ) )

		#write hotspot chunk
		f.write( struct.pack( '>3s', bytes( HOT_CHUNK, 'utf-8' ) ) )
		f.write( struct.pack( '>I', 1 ) )
		f.write( bytes( hotspot ) )


def write_hot_file( file, materials, hotspots ):
	if len( hotspots ) != len( materials ):
		raise RuntimeError

	with open( file, 'wb' ) as f:
		#write material chunk
		f.write( struct.pack( '>3s', bytes( MAT_CHUNK, 'utf-8' ) ) )
		f.write( struct.pack( '>I', len( materials ) ) )
		for matgroup in materials:
			f.write( struct.pack( '>I', len( matgroup ) ) )
			for mat in matgroup:
				size = len( mat )
				f.write( struct.pack( '>I', size ) )
				f.write( struct.pack( '>{}s'.format( size ), bytes( mat, 'utf-8' ) ) )

		#write hotspot chunk
		f.write( struct.pack( '>3s', bytes( HOT_CHUNK, 'utf-8' ) ) )
		f.write( struct.pack( '>I', len( hotspots ) ) )
		for h in hotspots:
			f.write( bytes( h ) )


def read_hot_file( file ):
	materials = []
	hotspots = []
	with open( file, 'rb' ) as f:
		data = f.read()

		offset = 0
		chunkname = struct.unpack_from( '>3s', data, offset )[0].decode( 'utf-8' )
		if chunkname == MAT_CHUNK:
			materials, offset = load_mat_subchunk( data, offset )
		
		chunkname = struct.unpack_from( '>3s', data, offset )[0].decode( 'utf-8' )
		if chunkname == HOT_CHUNK:
			hotspots, offset = load_hot_chunk( data, offset )

	return materials, hotspots


def get_hotfile_path():
	writable_dir = bpy.utils.extension_path_user( __package__, create=True )
	filepath = os.path.join( writable_dir, 'atlas_repo.hot' )
	if not os.path.isfile( filepath ):
		write_default_file( filepath )
	return filepath


def get_clipboardfile_path():
	writable_dir = bpy.utils.extension_path_user( __package__, create=True )
	filepath = os.path.join( writable_dir, 'atlas_clipboard.hot' )
	if not os.path.isfile( filepath ):
		write_default_file( filepath )
	return filepath


def load_hotspot_from_repo( material_name, material_aspect ):
	#load hotspot repo file
	hotfile = get_hotfile_path()
	existing_materials, existing_hotspots = read_hot_file( hotfile )

	hotspot_idx = -1
	for i in range( len( existing_materials ) ):
		if material_name in existing_materials[i]:
			hotspot_idx = i
			break
	if hotspot_idx < 0:
		return None
	
	existing_hotspots[hotspot_idx].applymaterialaspect( material_aspect )

	return existing_hotspots[hotspot_idx]


def get_hotspot( context ):
	rmmesh = rmlib.rmMesh.GetActive( context )
	if rmmesh is None:
		return None, None

	if context.scene.rmkituv_props.hotspotprops.hs_use_clipboard_atlas:
		hotfile = get_clipboardfile_path()
		existing_materials, existing_hotspots = read_hot_file( hotfile )

		selected_key = context.window_manager.generated_icon_hotspotclipboard
		selected_index = int( selected_key[-1] )

		h = existing_hotspots[selected_index]
		h.applymaterialaspect( 1.0 ) #hard coded for now. need to write aspect to the hotspot filetype

		hotspots = {}
		with rmmesh as rmmesh:
			rmmesh.readonly = True
			for f in rmmesh.bmesh.faces:
				if f.material_index not in hotspots:
					hotspots[f.material_index] = h

		return hotspots

	
	with rmmesh as rmmesh:
		rmmesh.readonly = True
		faces = rmlib.rmPolygonSet.from_selection( rmmesh )
		if len( faces ) <= 0:
			return None, None
		
		failed_midxs = set()
		hotspots = {}
		for f in faces:
			midx = f.material_index
			if midx in hotspots or midx in failed_midxs:
				continue

			try:
				material = rmmesh.mesh.materials[ midx ]
			except IndexError:
				continue

			material_aspect = 1.0
			try:
				material_aspect = material["WorldMappingWidth"] / material["WorldMappingHeight"]
			except:
				pass			
			
			hotspot = load_hotspot_from_repo( material.name, material_aspect )
			if hotspot is None:
				failed_midxs.add( midx )
				continue

			hotspots[midx] = hotspot
	
	return hotspots


def image_from_hotspot( hotspot, size=64 ):
	raw_data = [ 0.1 ] * 4 * size * size
	for b in hotspot:
		if b.width >= 1.0 or b.height >= 1.0:
			color = rmlib.util.HSV_to_RGB( random.random() * 0.01 , random.random() * 0.5 + 0.5, random.random() * 0.5 + 0.5 )
		else:
			color = rmlib.util.HSV_to_RGB( max( 0.4, random.random() ), random.random() * 0.5, random.random() * 0.5 + 0.5 )
		w = int( b.width * size )
		h = int( b.height * size )
		min_x = int( b.min[0] * size )
		min_y = int( b.min[1] * size )
		for m in range( h ):					
			y = min_y + m
			for n in range( w ):
				x = min_x + n
				idx = ( y * size + x ) * 4
				raw_data[ idx ] = color[0]
				raw_data[ idx + 1 ] = color[1]
				raw_data[ idx + 2 ] = color[2]
				raw_data[ idx + 3 ] = 1.0
	return raw_data


class OBJECT_OT_savehotspot( bpy.types.Operator ):
	"""Save the hotspot layout to the hotspot user config file."""
	bl_idname = 'object.savehotspot'
	bl_label = 'Create Hotspot'
	bl_options = { 'UNDO' }

	matname: bpy.props.StringProperty( name='Name' )

	@classmethod
	def poll( cls, context ):
		return ( context.active_object is not None and
				context.mode == 'OBJECT' and
				context.active_object.type == 'MESH' and
				len( context.active_object.data.materials ) > 0 )
	
	def draw( self, context ):
		self.layout.label( text='Save hotspot entry: \"{}\"?'.format( self.matname ) )

		thumb = self.__pcol[ 'save_hotspot_thumb' ]
		thumb.image_size = [ 128, 128 ]
		thumb.image_pixels_float = self.__save_thumb
		thumb.is_icon_custom = True	
		self.layout.template_icon( thumb.icon_id, scale=8.0 )
		self.layout.label( text='note: trim rects will have a very red hue in the thumbnail.' )

	def invoke(self, context, event):
		self.__save_thumb = []
		self.__trim_count = 0
		self.__pcol = bpy.utils.previews.new()
		self.__pcol.new( 'save_hotspot_thumb' )

		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:
			rmmesh.readonly = True

			if len( rmmesh.bmesh.loops.layers.uv.values() ) == 0:
				self.report( { 'WARNING' }, 'No uv data found!!!' )
				return { 'CANCELLED' }
			uvlayer = rmmesh.active_uv
			
			polys = rmlib.rmPolygonSet.from_mesh( rmmesh, filter_hidden=False )
			if len( polys ) == 0:
				self.report( { 'WARNING' }, 'No faces selected!!!' )
				return { 'CANCELLED' }

			self.__save_thumb.clear()
			self.__trim_count = 0
			hotspot = []
			for f in polys:
				uvlist = [ mathutils.Vector( l[uvlayer].uv.copy() ) for l in f.loops ]
				pmin = mathutils.Vector( uvlist[0] )
				pmax = mathutils.Vector( uvlist[0] )
				for p in uvlist:
					for i in range( 2 ):
						pmin[i] = min( pmin[i], p[i] )
						pmax[i] = max( pmax[i], p[i] )
				b = Bounds2d( [ pmin, pmax ] ).clamp()
				if b.width >= 1.0 or b.height >= 1.0:
					self.__trim_count += 1
				hotspot.append( b )
			self.__save_thumb = image_from_hotspot( hotspot, size=128 )

			try:
				self.matname = rmmesh.mesh.materials[ polys[0].material_index ].name
			except IndexError:
				self.report( { 'WARNING' }, 'Material lookup failed!!!' )
				return { 'CANCELLED' }
			
		return context.window_manager.invoke_props_dialog( self )

	def execute( self, context ):
		#generate new hotspot obj from face selection
		hotspot = None
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:
			rmmesh.readonly = True

			if len( rmmesh.bmesh.loops.layers.uv.values() ) == 0:
				return { 'CANCELLED' }
			uvlayer = rmmesh.active_uv
			
			polys = rmlib.rmPolygonSet.from_mesh( rmmesh, filter_hidden=False )
			if len( polys ) == 0:
				return { 'CANCELLED' }

			bounds = []
			for f in polys:
				uvlist = [ mathutils.Vector( l[uvlayer].uv.copy() ) for l in f.loops ]
				pmin = mathutils.Vector( uvlist[0] )
				pmax = mathutils.Vector( uvlist[0] )
				for p in uvlist:
					for i in range( 2 ):
						pmin[i] = min( pmin[i], p[i] )
						pmax[i] = max( pmax[i], p[i] )
				bounds.append( Bounds2d( [ pmin, pmax ] ).clamp() )

			try:
				mat_name = rmmesh.mesh.materials[ polys[0].material_index ].name
			except IndexError:
				self.report( { 'WARNING' }, 'Material lookup failed!!!' )
				return { 'CANCELLED' }
			hotspot = Hotspot( bounds, name=mat_name )

		#load hotspot repo file
		hotfile = get_hotfile_path()
		existing_materials, existing_hotspots = read_hot_file( hotfile )

		#remove matname from matgroup if it exists. it'll be added in later
		for i, matgrp in enumerate( existing_materials ):
			if mat_name in matgrp:
				existing_materials[i].remove( mat_name )
				if len( existing_materials[i] ) == 0:
					existing_materials.pop( i )
					existing_hotspots.pop( i )
				break

		'''
		#update hotspot database
		hotspot_already_exists = False
		for i, exhot in enumerate( existing_hotspots ):
			if exhot == hotspot:
				existing_materials[i].append( mat_name )
				hotspot_already_exists = True
				break
		if not hotspot_already_exists:
			existing_materials.append( [ mat_name ] )
			existing_hotspots.append( hotspot )
		'''

		#update hotspot database
		existing_materials.append( [ mat_name ] )
		existing_hotspots.append( hotspot )
		

		#write updated database
		write_hot_file( hotfile, existing_materials, existing_hotspots )
		self.report( { 'INFO' }, 'Hotspot Repo Updated!!! {} added'.format( mat_name ) )

		return  {'FINISHED' }


class OBJECT_OT_clipboardhotspot( bpy.types.Operator ):
	"""Save the hotspot layout to the clipbloard."""
	bl_idname = 'object.clipboardhotspot'
	bl_label = 'Clipboard Hotspot'
	bl_options = { 'UNDO' }

	@classmethod
	def poll( cls, context ):
		return ( context.active_object is not None and
				context.mode == 'OBJECT' and
				context.active_object.type == 'MESH' )

	def invoke(self, context, event):
		global custom_previews

		rmmesh = rmlib.rmMesh.GetActive( context )
		hotspot = None
		with rmmesh as rmmesh:
			rmmesh.readonly = True

			if len( rmmesh.bmesh.loops.layers.uv.values() ) == 0:
				self.report( { 'WARNING' }, 'No uv data found!!!' )
				return { 'CANCELLED' }
			uvlayer = rmmesh.active_uv
			
			polys = rmlib.rmPolygonSet.from_mesh( rmmesh, filter_hidden=False )
			if len( polys ) == 0:
				self.report( { 'WARNING' }, 'No faces selected!!!' )
				return { 'CANCELLED' }

			bounds = []			
			for f in polys:
				uvlist = [ mathutils.Vector( l[uvlayer].uv.copy() ) for l in f.loops ]
				pmin = mathutils.Vector( uvlist[0] )
				pmax = mathutils.Vector( uvlist[0] )
				for p in uvlist:
					for i in range( 2 ):
						pmin[i] = min( pmin[i], p[i] )
						pmax[i] = max( pmax[i], p[i] )
				bounds.append( Bounds2d( [ pmin, pmax ] ).clamp() )
				
			hotspot = Hotspot( bounds, name='clipboard' )

		if hotspot is None:
			return { 'CANCELLED' }

		#get selected preview image
		selected_key = context.window_manager.generated_icon_hotspotclipboard
		selected_index = int( selected_key[-1] )

		# Load it into the preview collection
		global preview_collections
		thumb = preview_collections['hs_clipboard'].get( 'clipboard0{}'.format( selected_index ) )

		size = 64
		thumb.image_size = [ size, size ]
		raw_data = image_from_hotspot( bounds, size=size )
		thumb.image_pixels_float = raw_data
		thumb.is_icon_custom = True

		#load hotspot repo file
		hotfile = get_clipboardfile_path()
		existing_materials, existing_hotspots = read_hot_file( hotfile )

		#update hotspot database
		for i in range( 4 ):
			try:
				existing_materials[i] = 'clipboard0{}'.format( i )
			except IndexError:
				existing_materials.append( 'clipboard0{}'.format( i ) )
				existing_hotspots.append( Hotspot( [], name='clipboard0{}'.format( i ) ) )

			if i == selected_index:
				existing_hotspots[i] = hotspot	

		#write updated database
		write_hot_file( hotfile, existing_materials, existing_hotspots )
		self.report( { 'INFO' }, 'Clipboard Hotspot written to repo file!!!' )

		global update_clipboard_thumbs
		update_clipboard_thumbs = True

		return  {'FINISHED' }


class OBJECT_OT_repotoascii( bpy.types.Operator ):
	"""Convert the binary hotspot cfg file to ascii for debugging."""
	bl_idname = 'mesh.repotoascii'
	bl_label = 'Hotspot Repo to Ascii'
	
	filter_glob: bpy.props.StringProperty( default='*.txt', options={ 'HIDDEN' } )
	filepath: bpy.props.StringProperty( name="File Path", description="", maxlen= 1024, default= "" )
	files: bpy.props.CollectionProperty( name = 'File Path', type = bpy.types.OperatorFileListElement )

	@classmethod
	def poll( cls, context ):
		return True

	def execute( self, context ):
		#load hotspot repo file
		hotfile = get_hotfile_path()
		existing_materials, existing_hotspots = read_hot_file( hotfile )

		if not self.filepath.endswith( '.txt' ):
			self.filepath += '.txt'

		#write ascii file
		with open( self.filepath, 'w' ) as f:
			f.write( MAT_CHUNK + '\n' )
			for i, matgroup in enumerate( existing_materials ):
				f.write( '\t{}\n'.format( i ) )
				for mat in matgroup:
					f.write( '\t\t{}\n'.format( mat ) )

			f.write( '\n' + HOT_CHUNK + '\n' )
			for hotspot in existing_hotspots:
				f.write( str( hotspot ) )
				f.write( '\n\n' )

		return  {'FINISHED' }

	def invoke( self, context, event ):
		wm = context.window_manager
		wm.fileselect_add( self )
		return { 'RUNNING_MODAL' }


class MESH_OT_grabapplyuvbounds( bpy.types.Operator ):
	"""Fit the selected uvfaces to the bounds of the uv island of the faces under the mouse in the 3d view."""
	bl_idname = 'mesh.grabapplyuvbounds'
	bl_label = 'GrabApplyUVBounds (MOS)'
	bl_options = { 'UNDO' }

	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'VIEW_3D' and
				context.active_object is not None and
				context.active_object.type == 'MESH' )

	def execute( self, context ):
		sel_mode = context.tool_settings.mesh_select_mode[:]
		if not sel_mode[2]:
			return { 'CANCELLED' }

		#get target_bounds from MOS
		mouse_pos = mathutils.Vector( ( float( self.mos[0] ), float( self.mos[1] ) ) )
		mos_rmmesh = rmlib.rmMesh.from_mos( context, mouse_pos )
		if mos_rmmesh is None:
			return { 'CANCELLED' }
		with mos_rmmesh as rmmesh:
			rmmesh.readonly = True
			if len( rmmesh.bmesh.loops.layers.uv ) < 1:
				return { 'CANCELLED' }
			uvlayer = rmmesh.active_uv
		
			faces = rmlib.rmPolygonSet.from_mos( rmmesh, context, mouse_pos )
			if len( faces ) < 1:
				return { 'CANCELLED' }
			
			target_faces = faces.island( uvlayer, element=True )[0]
			target_loops = set()
			for f in target_faces:
				for l in f.loops:
					target_loops.add( l )
			target_bounds = Bounds2d.from_loops( target_loops, uvlayer )

		#move selection to target_bounds
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:
			uvlayer = rmmesh.active_uv

			source_faces = rmlib.rmPolygonSet.from_selection( rmmesh )
			for source_island in source_faces.island( uvlayer ):
				loops = set()
				for f in source_island:
					for l in f.loops:
						loops.add( l )
				source_bounds = Bounds2d.from_loops( loops, uvlayer )

				mat = source_bounds.transform( target_bounds )		
				for l in loops:
					uv = mathutils.Vector( l[uvlayer].uv.copy() ).to_3d()
					uv[2] = 1.0
					uv = mat @ uv
					l[uvlayer].uv = uv.to_2d()

		return { 'FINISHED' }

	def invoke( self, context, event ):
		self.mos = ( event.mouse_region_x, event.mouse_region_y )
		return self.execute( context )


class MESH_OT_moshotspot( bpy.types.Operator ):
	"""Map the selected uvfaces to the hotspot under the cursor in the uv view using the atlas defined by the material on the uvfaces."""
	bl_idname = 'mesh.moshotspot'
	bl_label = 'Hotspot (MOS)'
	bl_options = { 'UNDO' }

	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'IMAGE_EDITOR' and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):
		sel_mode = context.tool_settings.mesh_select_mode[:]
		if not sel_mode[2]:
			return { 'CANCELLED' }

		hotspot_dict = get_hotspot( context )
		if len( hotspot_dict ) < 1:
			return { 'CANCELLED' }

		use_trim = context.scene.rmkituv_props.hotspotprops.hs_recttype_filter != 'notrim'		

		#if multiUV get the selected hotspot from the clipboard in case a uv mode is set to clipboard
		clipboard_hotspot = None
		uv_modes = ( context.scene.rmkituv_props.hotspotprops.hs_hotspot_uv1, context.scene.rmkituv_props.hotspotprops.hs_hotspot_uv2 )
		if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
			if uv_modes[0] == 'none' and uv_modes[1] == 'none':
				self.repo( {'ERROR'}, 'Could not hotspot multiUV match because both uv enums set to None!!!' )
				return { 'CANCELLED' }

			if 'clipboard' in uv_modes:
				selected_key = context.window_manager.generated_icon_hotspotclipboard
				selected_index = int( selected_key[-1] )
				existing_clipboard_materials, existing_clipboard_hotspots = read_hot_file( get_clipboardfile_path() )
				clipboard_hotspot = existing_clipboard_hotspots[selected_index]

		uvlayers = []
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:
			uvlayer = rmmesh.active_uv

			#if multiUV, get uvlayers to look up if the active_uv is set to clipboard
			if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
				for i, uvmode in enumerate( uv_modes ):
					try:
						uvlayers.append( rmmesh.bmesh.loops.layers.uv.values()[i] )
					except IndexError:
						uvlayers.append( rmmesh.bmesh.loops.layers.uv.new( 'UVMap' ) )
			
			faces = GetFaceSelection( context, rmmesh )
			if len( faces ) < 1:
				return { 'CANCELLED' }

			for island in faces.island( uvlayer ):
				hotspot = None
				if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
					if uvlayer.name == uvlayers[0].name and uv_modes[0] == 'clipboard':
						hotspot = clipboard_hotspot
					elif uvlayer.name == uvlayers[1].name and uv_modes[1] == 'clipboard':
						hotspot = clipboard_hotspot
					else:
						try:
							hotspot = hotspot_dict[island[0].material_index]
						except KeyError:
							self.report( { 'WARNING' }, 'Hotspot atlas not found for {}'.format( rmmesh.mesh.materials[island[0].material_index].name ) )
							continue
				else:
					try:
						hotspot = hotspot_dict[island[0].material_index]
					except KeyError:
						self.report( { 'WARNING' }, 'Hotspot atlas not found for {}'.format( rmmesh.mesh.materials[island[0].material_index].name ) )
						continue

				target_bounds = hotspot.nearest( self.mos_uv[0], self.mos_uv[1] ).copy()

				loops = set()
				for f in island:
					for l in f.loops:
						loops.add( l )
				source_bounds = Bounds2d.from_loops( loops, uvlayer, materialaspect=hotspot.materialaspect )

				mat = source_bounds.transform( target_bounds, skip_rot=False, trim=use_trim, inset=context.scene.rmkituv_props.hotspotprops.hs_hotspot_inset / 1024.0, random_rot=context.scene.rmkituv_props.hotspotprops.hs_random_rotation, random_flip=context.scene.rmkituv_props.hotspotprops.hs_random_flip )
				for l in loops:
					uv = mathutils.Vector( l[uvlayer].uv.copy() ).to_3d()
					uv[2] = 1.0
					uv = mat @ uv
					l[uvlayer].uv = uv.to_2d()

		return { 'FINISHED' }

	def invoke( self, context, event ):
		self.mos_uv = context.region.view2d.region_to_view( event.mouse_region_x, event.mouse_region_y )
		return self.execute( context )


class MESH_OT_nrsthotspot( bpy.types.Operator ):
	"""Use the hotspot nearest to the selected uv faces in the atlas defined by its material."""
	bl_idname = 'mesh.nrsthotspot'
	bl_label = 'Hotspot Nrst'
	bl_options = { 'UNDO' }

	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'IMAGE_EDITOR' and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):
		sel_mode = context.tool_settings.mesh_select_mode[:]
		if not sel_mode[2]:
			return { 'CANCELLED' }

		hotspot_dict = get_hotspot( context )
		if len( hotspot_dict ) < 1:
			return { 'CANCELLED' }

		use_trim = context.scene.rmkituv_props.hotspotprops.hs_recttype_filter != 'notrim'

		#if multiUV get the selected hotspot from the clipboard in case a uv mode is set to clipboard
		clipboard_hotspot = None
		uv_modes = ( context.scene.rmkituv_props.hotspotprops.hs_hotspot_uv1, context.scene.rmkituv_props.hotspotprops.hs_hotspot_uv2 )
		if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
			if uv_modes[0] == 'none' and uv_modes[1] == 'none':
				self.repo( {'ERROR'}, 'Could not hotspot multiUV match because both uv enums set to None!!!' )
				return { 'CANCELLED' }

			if 'clipboard' in uv_modes:
				selected_key = context.window_manager.generated_icon_hotspotclipboard
				selected_index = int( selected_key[-1] )
				existing_clipboard_materials, existing_clipboard_hotspots = read_hot_file( get_clipboardfile_path() )
				clipboard_hotspot = existing_clipboard_hotspots[selected_index]

		uvlayers = []
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:
			uvlayer = rmmesh.active_uv

			#if multiUV, get uvlayers to look up if the active_uv is set to clipboard
			if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
				for i, uvmode in enumerate( uv_modes ):
					try:
						uvlayers.append( rmmesh.bmesh.loops.layers.uv.values()[i] )
					except IndexError:
						uvlayers.append( rmmesh.bmesh.loops.layers.uv.new( 'UVMap' ) )
			
			faces = GetFaceSelection( context, rmmesh )
			if len( faces ) < 1:
				return { 'CANCELLED' }

			for island in faces.island( uvlayer ):
				hotspot = None
				if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
					if uvlayer.name == uvlayers[0].name and uv_modes[0] == 'clipboard':
						hotspot = clipboard_hotspot
					elif uvlayer.name == uvlayers[1].name and uv_modes[1] == 'clipboard':
						hotspot = clipboard_hotspot
					else:
						try:
							hotspot = hotspot_dict[island[0].material_index]
						except KeyError:
							self.report( { 'WARNING' }, 'Hotspot atlas not found for {}'.format( rmmesh.mesh.materials[island[0].material_index].name ) )
							continue
				else:
					try:
						hotspot = hotspot_dict[island[0].material_index]
					except KeyError:
						self.report( { 'WARNING' }, 'Hotspot atlas not found for {}'.format( rmmesh.mesh.materials[island[0].material_index].name ) )
						continue

				loops = set()
				for f in island:
					for l in f.loops:
						loops.add( l )
				source_bounds = Bounds2d.from_loops( loops, uvlayer, materialaspect=hotspot.materialaspect )
				target_bounds = hotspot.nearest( source_bounds.center.x, source_bounds.center.y ).copy()
				mat = source_bounds.transform( target_bounds, skip_rot=True, trim=use_trim, inset=context.scene.rmkituv_props.hotspotprops.hs_hotspot_inset / 1024.0 )
				for l in loops:
					uv = mathutils.Vector( l[uvlayer].uv.copy() ).to_3d()
					uv[2] = 1.0
					uv = mat @ uv
					l[uvlayer].uv = uv.to_2d()

		return { 'FINISHED' }
	

class MESH_OT_matchhotspot( bpy.types.Operator ):
	"""Map the current face selection to the best fit hotspot on the atlas defined by the material."""
	bl_idname = 'mesh.matchhotspot'
	bl_label = 'Hotspot Match'
	bl_options = { 'UNDO' }

	tollerance: bpy.props.FloatProperty(
		name='Tollerance',
		default=0.01
	)

	@classmethod
	def poll( cls, context ):
		return ( ( context.area.type == 'VIEW_3D' or context.area.type == 'IMAGE_EDITOR' ) and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )

	def execute( self, context ):
		sel_mode = context.tool_settings.mesh_select_mode[:]
		if not sel_mode[2]:
			self.report( { 'WARNING' }, 'Must be in face selection mode.' )
			return { 'CANCELLED' }

		hotspot_dict = get_hotspot( context )
		if len( hotspot_dict ) < 1:
			self.report( { 'WARNING' }, 'Could not find hotspot atlas!!!' )
			return { 'CANCELLED' }

		use_trim = context.scene.rmkituv_props.hotspotprops.hs_recttype_filter != 'notrim'

		uvlayers = []

		#preprocess uvs
		clipboard_hotspot = None
		islands_as_indexes = []
		if context.area.type == 'VIEW_3D': #if in 3dvp, scale to mat size then rectangularize/gridify uv islands

			uv_modes = ( 'hotspot', 'hotspot' )
			if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
				uv_modes = ( context.scene.rmkituv_props.hotspotprops.hs_hotspot_uv1, context.scene.rmkituv_props.hotspotprops.hs_hotspot_uv2 )
				if uv_modes[0] == 'none' and uv_modes[1] == 'none':
					self.repo( {'ERROR'}, 'Could not hotspot multiUV match because both uv enums set to None!!!' )
					return { 'CANCELLED' }
			elif context.scene.rmkituv_props.hotspotprops.hs_use_clipboard_atlas:
				uv_modes = ( 'clipboard', 'clipboard' )

			if 'clipboard' in uv_modes:
				selected_key = context.window_manager.generated_icon_hotspotclipboard
				selected_index = int( selected_key[-1] )
				existing_clipboard_materials, existing_clipboard_hotspots = read_hot_file( get_clipboardfile_path() )
				clipboard_hotspot = existing_clipboard_hotspots[selected_index]
			
			rmmesh = rmlib.rmMesh.GetActive( context )
			with rmmesh as rmmesh:
				rmmesh.readonly = True
				if len( rmmesh.bmesh.loops.layers.uv.values() ) == 0:
					self.report( { 'WARNING' }, 'No uv data found!!!' )
					return { 'CANCELLED' }				

				if context.scene.rmkituv_props.hotspotprops.hs_use_multiUV:
					for i, uvmode in enumerate( uv_modes ):
						if uvmode != 'none':
							try:
								uvlayers.append( rmmesh.bmesh.loops.layers.uv.values()[i] )
							except IndexError:
								uvlayers.append( rmmesh.bmesh.loops.layers.uv.new( 'UVMap' ) )
				else:
					uvlayers.append( rmmesh.active_uv )

				faces = rmlib.rmPolygonSet.from_selection( rmmesh )
				if len( faces ) < 1:
					self.report( { 'WARNING' }, 'No faces selected!!!' )
					return { 'CANCELLED' }

				auto_smooth_angle = math.pi
				if bpy.app.version < (4,0,0) and rmmesh.mesh.use_auto_smooth:
					auto_smooth_angle = rmmesh.mesh.auto_smooth_angle

				current_active_layer_index = rmmesh.mesh.uv_layers.active_index
				for island in faces.group( element=False, use_seam=True, use_material=True, use_sharp=True, use_angle=auto_smooth_angle ):
					islands_as_indexes.append( [ f.index for f in island ] )					
					island.select( replace=True )
					for i, uvlayer in enumerate( uvlayers ):
						if not context.scene.rmkituv_props.hotspotprops.hs_use_multiUV or uv_modes[i] == 'hotspot' or uv_modes[i] == 'clipboard':
							result = bpy.ops.mesh.rm_uvgridify( uv_map_name=uvlayer.name ) #gridify
							if result == { 'CANCELLED' }:
								rmmesh.mesh.uv_layers.active_index = i
								bpy.ops.uv.unwrap( 'INVOKE_DEFAULT', method='CONFORMAL' )
								bpy.ops.mesh.rm_uvunrotate() #unrotate uv by longest edge in island
								#bpy.ops.mesh.rm_uvrectangularize() #rectangularize
							bpy.ops.mesh.rm_normalizetexels( uv_map_name=uvlayer.name ) #account for non-square materials
							bpy.ops.mesh.rm_scaletomaterialsize( uv_map_name=uvlayer.name ) #scale to mat size
						elif uv_modes[i] == 'worldspace':
							bpy.ops.mesh.rm_worldspaceproject( uv_map_name=uvlayer.name )
				rmmesh.mesh.uv_layers.active_index = current_active_layer_index

		elif context.area.type == 'IMAGE_EDITOR': #if in uvvp, scale to mat sizecomplete_failure
			rmmesh = rmlib.rmMesh.GetActive( context )
			with rmmesh as rmmesh:
				rmmesh.readonly = True
				if len( rmmesh.bmesh.loops.layers.uv.values() ) == 0:
					self.report( { 'WARNING' }, 'No uv data found!!!' )
					return { 'CANCELLED' }

				uvlayers.append( rmmesh.active_uv )

				faces = GetFaceSelection( context, rmmesh )
				if len( faces ) < 1:
					self.report( { 'WARNING' }, 'No uv faces selected!!!' )
					return { 'CANCELLED' }
				for island in faces.island( uvlayers[0], use_seam=True ):
					islands_as_indexes.append( [ f.index for f in island ] )
					#island.select( replace=True )
					#bpy.ops.mesh.rm_scaletomaterialsize() #scale to mat size
					
		#hotspot
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:
			if context.area.type == 'VIEW_3D':
				initial_selection = []
				for pidx_list in islands_as_indexes:
					island = [ rmmesh.bmesh.faces[pidx] for pidx in pidx_list ]

					try:
						hotspot = hotspot_dict[island[0].material_index]
					except KeyError:
						self.report( { 'WARNING' }, 'Hotspot atlas not found for {}'.format( rmmesh.mesh.materials[island[0].material_index].name ) )
						continue

					initial_selection += set( island )
					loops = []
					for f in island:
						for l in f.loops:
							loops.append( l )
					for i, uvlayer in enumerate( uvlayers ):
						if not context.scene.rmkituv_props.hotspotprops.hs_use_multiUV or ( uv_modes[i] == 'hotspot' or uv_modes[i] == 'clipboard' ):
							source_bounds = Bounds2d.from_loops( loops, uvlayer, materialaspect=hotspot.materialaspect )
							if source_bounds.area <= 0.00001:
								continue
							if uv_modes[i] == 'hotspot':
								target_bounds = hotspot.match( source_bounds, tollerance=self.tollerance, trim_filter=context.scene.rmkituv_props.hotspotprops.hs_recttype_filter ).copy()
							elif uv_modes[i] == 'clipboard':
								target_bounds = clipboard_hotspot.match( source_bounds, tollerance=self.tollerance, trim_filter=context.scene.rmkituv_props.hotspotprops.hs_recttype_filter ).copy()
							if target_bounds is None:
								self.report( { 'WARNING' }, 'Could not find a hotspot match for a uvisland!!!' )
								continue
							mat = source_bounds.transform( target_bounds, skip_rot=False, trim=use_trim, inset=context.scene.rmkituv_props.hotspotprops.hs_hotspot_inset / 1024.0, random_rot=context.scene.rmkituv_props.hotspotprops.hs_random_rotation, random_flip=context.scene.rmkituv_props.hotspotprops.hs_random_flip )
							for l in loops:
								uv = mathutils.Vector( l[uvlayer].uv.copy() ).to_3d()
								uv[2] = 1.0
								uv = mat @ uv
								l[uvlayer].uv = uv.to_2d()

				for f in initial_selection:
					f.select = True

			elif context.area.type == 'IMAGE_EDITOR':
				uvlayer = uvlayers[0]
				initial_selection = []
				for pidx_list in islands_as_indexes:					
					island = [ rmmesh.bmesh.faces[pidx] for pidx in pidx_list ]

					try:
						hotspot = hotspot_dict[island[0].material_index]
					except KeyError:
						self.report( { 'WARNING' }, 'Hotspot atlas not found for {}'.format( rmmesh.mesh.materials[island[0].material_index].name ) )
						continue

					initial_selection += set( island )
					loops = []
					for f in island:
						for l in f.loops:
							loops.append( l )
					source_bounds = Bounds2d.from_loops( loops, uvlayer, materialaspect = hotspot.materialaspect )
					target_bounds = hotspot.match( source_bounds, tollerance=self.tollerance, trim_filter=context.scene.rmkituv_props.hotspotprops.hs_recttype_filter ).copy()
					if target_bounds is None:
						self.report( { 'WARNING' }, 'Could not find a hotspot match for a uvisland!!!' )
						continue
					mat = source_bounds.transform( target_bounds, skip_rot=False, trim=use_trim, inset=context.scene.rmkituv_props.hotspotprops.hs_hotspot_inset / 1024.0, random_rot=context.scene.rmkituv_props.hotspotprops.hs_random_rotation, random_flip=context.scene.rmkituv_props.hotspotprops.hs_random_flip )		
					for l in loops:
						uv = mathutils.Vector( l[uvlayer].uv.copy() ).to_3d()
						uv[2] = 1.0
						uv = mat @ uv
						l[uvlayer].uv = uv.to_2d()

				for f in initial_selection:
					f.select = True

		return { 'FINISHED' }


class MESH_OT_uvaspectscale( bpy.types.Operator ):
	"""Inset Selected UV Islands"""
	bl_idname = 'mesh.rm_uvaspectscale'
	bl_label = 'UV Aspect Scale'
	bl_options = { 'REGISTER', 'UNDO' }
	
	scale: bpy.props.FloatProperty(
		name='Inset',
		default=0.0
	)

	def cancel( self, context ):
		if hasattr( self, 'bmesh' ):
			if self.bmesh is not None:
				self.bmesh.free()
	
	@classmethod
	def poll( cls, context ):
		return ( context.area.type == 'IMAGE_EDITOR' and
				context.active_object is not None and
				context.active_object.type == 'MESH' and
				context.object.data.is_editmode )
		
	def execute( self, context ):
		offset = self.scale / 10.0
		if self.shift_sensitivity:
			offset /= 10.0

		targetObj = context.active_object
		targetMesh = targetObj.data

		bpy.ops.object.mode_set( mode='OBJECT', toggle=False )
		
		bm = self.bmesh.copy()
		
		uvlayer = bm.loops.layers.uv.verify()
		
		rmmesh = rmlib.rmMesh.from_bmesh( targetObj, bm )
		faces = GetFaceSelection( context, rmmesh )
		if len( faces ) < 1:
			bpy.ops.object.mode_set( mode='EDIT', toggle=False )
			return { 'CANCELLED' }

		for island in faces.island( uvlayer ):

			#get the material aspect ratio on the first poly of this island
			material_aspect = 1.0
			try:
				material = rmmesh.mesh.materials[island[0].material_index]
			except IndexError:
				pass
			try:
				material_aspect = material["WorldMappingWidth"] / material["WorldMappingHeight"]
			except:
				pass

			loops = set()
			for f in island:
				for l in f.loops:
					loops.add( l )
			source_bounds = Bounds2d.from_loops( loops, uvlayer, materialaspect=material_aspect )

			new_min = source_bounds.min.copy()
			new_min[0] += offset
			new_min[1] += offset

			new_max = source_bounds.max.copy()
			new_max[0] -= offset
			new_max[1] -= offset

			target_bounds = Bounds2d( [ new_min, new_max ] )
			target_bounds.materialaspect = source_bounds.materialaspect

			mat = source_bounds.transform( target_bounds, skip_rot=True, trim=False, inset=0.0 )		
			for l in loops:
				uv = mathutils.Vector( l[uvlayer].uv.copy() ).to_3d()
				uv[2] = 1.0
				uv = mat @ uv
				l[uvlayer].uv = uv.to_2d()

		
		bm.to_mesh( targetMesh )
		bm.calc_loop_triangles()
		targetMesh.update()
		bm.free()
		
		bpy.ops.object.mode_set( mode='EDIT', toggle=False )
		
		return { 'FINISHED' }

	def modal( self, context, event ):
		if event.type == 'LEFTMOUSE':
			return { 'FINISHED' }
		elif event.type == 'MOUSEMOVE':
			self.shift_sensitivity = event.shift
			delta_x = float( event.mouse_x - event.mouse_prev_press_x ) / context.region.width
			if delta_x != self.prev_delta:
				self.prev_delta = delta_x
				self.scale = delta_x * 4.0
				self.execute( context )			
		elif event.type == 'ESC':
			return { 'CANCELLED' }

		return { 'RUNNING_MODAL' }
	
	def invoke( self, context, event ):
		self.bmesh = None
		self.prev_delta = 0
		self.shift_sensitivity = False

		if context.object is None or context.mode == 'OBJECT':
			return { 'CANCELLED' }
		
		if context.object.type != 'MESH':
			return { 'CANCELLED' }

		sel_mode = context.tool_settings.mesh_select_mode[:]
		if not sel_mode[2]:
			return { 'CANCELLED' }

		rmmesh = rmlib.rmMesh.GetActive( context )
		if rmmesh is not None:
			with rmmesh as rmmesh:
				rmmesh.readme = True
				self.bmesh = rmmesh.bmesh.copy()
				
		context.window_manager.modal_handler_add( self )
		return { 'RUNNING_MODAL' }
		

def enum_previews_from_directory_items( self, context ):
	enum_items = []

	if context is None:
		return enum_items	

	hotfile = get_hotfile_path()
	existing_materials, existing_hotspots = read_hot_file( hotfile )
	
	size = 64
	pcoll = preview_collections["main"]
	for i in range( len( existing_hotspots ) ):
		name = str( i )
		icon = pcoll.get( name )
		if not icon:
			thumb = pcoll.new( name )
			thumb.image_size = [ size, size ]
			thumb.image_pixels_float = image_from_hotspot( existing_hotspots[i].data )
			thumb.is_icon_custom = True			
		else:
			thumb = pcoll[name]
		enum_items.append( ( name, name, "", thumb.icon_id, i ) )

	pcoll.my_previews = enum_items
	return pcoll.my_previews


class MESH_OT_refhostpot( bpy.types.Operator ):
	"""Make the material on the current face selection use an existing hotspot layout."""
	bl_idname = 'mesh.refhotspot'
	bl_label = 'Ref Hotspot'
	bl_options = { 'UNDO' }

	my_previews: bpy.props.EnumProperty( items=enum_previews_from_directory_items )

	@classmethod
	def poll( cls, context ):
		return ( context.active_object is not None and
				context.mode in ['OBJECT', 'EDIT_MESH' ] and
				context.active_object.type == 'MESH' and
				len( context.active_object.data.materials ) > 0 )

	def execute( self, context ):		
		img_name = self.my_previews

		#get material name
		rmmesh = rmlib.rmMesh.GetActive( context )
		with rmmesh as rmmesh:
			rmmesh.readonly = True
			
			mat_name = ''
			if context.mode == 'EDIT_MESH':
				polys = rmlib.rmPolygonSet.from_selection( rmmesh )
				if len( polys ) == 0:
					self.report( { 'ERROR' }, 'Must have at least one face selected!!!' )
					return { 'CANCELLED' }
				try:
					mat_name = rmmesh.mesh.materials[ polys[0].material_index ].name
				except KeyError:
					self.report( { 'ERROR' }, 'Material index on face out of bounds!!!' )
					return { 'CANCELLED' }
				except IndexError:
					self.report( { 'ERROR' }, 'Material index on face out of bounds!!!' )
					return { 'CANCELLED' }
			elif context.mode == 'OBJECT':
				try:
					mat_name = rmmesh.mesh.materials[ rmmesh.bmesh.faces[0].material_index ].name
				except KeyError:
					self.report( { 'ERROR' }, 'Material index on face out of bounds!!!' )
					return { 'CANCELLED' }
				except IndexError:
					self.report( { 'ERROR' }, 'Material index on face out of bounds!!!' )
					return { 'CANCELLED' }
				

		#load hotspot repo file
		hotfile = get_hotfile_path()
		existing_materials, existing_hotspots = read_hot_file( hotfile )

		#remove matname from matgroup if it exists. it'll be added in later
		for i, matgrp in enumerate( existing_materials ):
			if mat_name in matgrp:
				existing_materials[i].remove( mat_name )

		#update hotspot database
		hotspot_idx = int( img_name )
		if hotspot_idx < len( existing_materials ):
			existing_materials[hotspot_idx].append( mat_name )		

		#write updated database
		write_hot_file( hotfile, existing_materials, existing_hotspots )
		self.report( { 'WARNING' }, 'Hotspot Repo Updated!!!' )

		return  {'FINISHED' }

	def draw(self, context):
		layout = self.layout
		layout.template_icon_view( self, "my_previews" )

	def invoke( self, context, event ):
		random.seed( 0 )
		return context.window_manager.invoke_props_dialog( self, width=128 )


preview_collections = {}


class UV_PT_UVHotspotTools( bpy.types.Panel ):
	bl_parent_id = 'UV_PT_RMKITUV_PARENT'
	bl_idname = 'UV_PT_UVHotspotTools'
	bl_label = 'Hotspot'
	bl_region_type = 'UI'
	bl_space_type = 'IMAGE_EDITOR'
	#bl_options = { 'DEFAULT_CLOSED' }

	def draw( self, context ):
		layout = self.layout

		layout.template_icon_view( context.window_manager, "generated_icon_hotspotclipboard", show_labels=True, scale=4.0, scale_popup=4.0)

		layout = layout.column()
		layout.operator( OBJECT_OT_clipboardhotspot.bl_idname )			
		layout.prop( context.scene.rmkituv_props.hotspotprops, 'hs_use_clipboard_atlas' )

		layout.separator()

		r1 = layout.row()
		r1.prop( context.scene.rmkituv_props.hotspotprops, 'hs_recttype_filter' )
		r1.prop( context.scene.rmkituv_props.hotspotprops, 'hs_hotspot_inset' )

		r2 = layout.row()
		r2.prop( context.scene.rmkituv_props.hotspotprops, 'hs_random_rotation' )
		r2.prop( context.scene.rmkituv_props.hotspotprops, 'hs_random_flip' )

		layout.separator()

		layout.operator( 'object.savehotspot', text='New Hotspot' )
		layout.operator( 'mesh.refhotspot', text='Ref Hotspot' )
		layout.operator( 'mesh.matchhotspot', text='Hotspot Match' )
		layout.operator( 'mesh.nrsthotspot', text='Hotspot Nearest' )


class VIEW3D_PT_UVHotspotTools( bpy.types.Panel ):
	bl_parent_id = 'VIEW3D_PT_RMKITUV_PARENT'
	bl_idname = 'VIEW3D_PT_UVHotspotTools'
	bl_label = 'Hotspot'
	bl_region_type = 'UI'
	bl_space_type = 'VIEW_3D'
	#bl_options = { 'DEFAULT_CLOSED' }

	def draw( self, context ):
		layout = self.layout
		
		layout.template_icon_view( context.window_manager, "generated_icon_hotspotclipboard", show_labels=True, scale=4.0, scale_popup=4.0)

		layout = layout.column()
		layout.operator( OBJECT_OT_clipboardhotspot.bl_idname )			
		layout.prop( context.scene.rmkituv_props.hotspotprops, 'hs_use_clipboard_atlas' )

		layout.separator()

		r1 = layout.row()
		r1.prop( context.scene.rmkituv_props.hotspotprops, 'hs_recttype_filter' )
		r1.prop( context.scene.rmkituv_props.hotspotprops, 'hs_hotspot_inset' )

		r2 = layout.row()
		r2.prop( context.scene.rmkituv_props.hotspotprops, 'hs_random_rotation' )
		r2.prop( context.scene.rmkituv_props.hotspotprops, 'hs_random_flip' )

		layout.separator()

		layout.operator( 'object.savehotspot', text='New Hotspot' )
		layout.operator( 'mesh.refhotspot', text='Ref Hotspot' )

		layout.separator()

		r3 = layout.row()
		r3.prop( context.scene.rmkituv_props.hotspotprops, 'hs_use_multiUV' )
		r3.enabled = not context.scene.rmkituv_props.hotspotprops.hs_use_clipboard_atlas
		r4 = layout.row()
		r4.prop( context.scene.rmkituv_props.hotspotprops, 'hs_hotspot_uv1' )
		r4.prop( context.scene.rmkituv_props.hotspotprops, 'hs_hotspot_uv2' )
		r4.enabled = context.scene.rmkituv_props.hotspotprops.hs_use_multiUV and not context.scene.rmkituv_props.hotspotprops.hs_use_clipboard_atlas
		layout.operator( 'mesh.matchhotspot' )


update_clipboard_thumbs = True

def enum_previews_hotspot_clipboardfile( self, context ):
	global update_clipboard_thumbs
	if not update_clipboard_thumbs:
		return preview_collections["hs_clipboard"].my_previews
	update_clipboard_thumbs = False
	
	enum_items = []

	if context is None:
		return enum_items	

	hotfile = get_clipboardfile_path()
	existing_materials, existing_hotspots = read_hot_file( hotfile )
	
	size = 64
	pcoll = preview_collections["hs_clipboard"]
	for i in range( 4 ):
		name = 'clipboard0{}'.format( i )
		thumb = pcoll.get( name )
		thumb.image_size = [ size, size ]
		try:
			thumb.image_pixels_float = image_from_hotspot( existing_hotspots[i].data )
		except:
			pass
		thumb.is_icon_custom = True
		enum_items.append( ( name, name, "", thumb.icon_id, i ) )

	pcoll.my_previews = enum_items
	return pcoll.my_previews

def register():
	bpy.utils.register_class( OBJECT_OT_savehotspot )
	bpy.utils.register_class( MESH_OT_matchhotspot )
	bpy.utils.register_class( MESH_OT_nrsthotspot )
	bpy.utils.register_class( MESH_OT_moshotspot )
	bpy.utils.register_class( MESH_OT_grabapplyuvbounds )
	bpy.utils.register_class( UV_PT_UVHotspotTools )
	bpy.utils.register_class( VIEW3D_PT_UVHotspotTools )
	bpy.utils.register_class( OBJECT_OT_repotoascii )
	bpy.utils.register_class( MESH_OT_uvaspectscale )
	bpy.utils.register_class( OBJECT_OT_clipboardhotspot )

	pcoll = bpy.utils.previews.new()
	pcoll.my_previews = ()
	preview_collections["main"] = pcoll
	bpy.utils.register_class( MESH_OT_refhostpot )

	pcol2 = bpy.utils.previews.new()
	pcol2.new( 'clipboard00' )
	pcol2.new( 'clipboard01' )
	pcol2.new( 'clipboard02' )
	pcol2.new( 'clipboard03' )
	preview_collections["hs_clipboard"] = pcol2

	bpy.types.WindowManager.generated_icon_hotspotclipboard = bpy.props.EnumProperty(items=enum_previews_hotspot_clipboardfile)


def unregister():
	bpy.utils.unregister_class( OBJECT_OT_savehotspot )
	bpy.utils.unregister_class( MESH_OT_matchhotspot )
	bpy.utils.unregister_class( MESH_OT_nrsthotspot )
	bpy.utils.unregister_class( MESH_OT_moshotspot )
	bpy.utils.unregister_class( MESH_OT_grabapplyuvbounds )
	bpy.utils.unregister_class( UV_PT_UVHotspotTools )
	bpy.utils.unregister_class( VIEW3D_PT_UVHotspotTools )
	bpy.utils.unregister_class( OBJECT_OT_repotoascii )
	bpy.utils.unregister_class( MESH_OT_uvaspectscale )
	bpy.utils.unregister_class( OBJECT_OT_clipboardhotspot )

	for pcol in preview_collections.values():
		bpy.utils.previews.remove(pcol)
	preview_collections.clear()
	bpy.utils.unregister_class( MESH_OT_refhostpot )