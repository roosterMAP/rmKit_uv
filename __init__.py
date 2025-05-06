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
import os
import threading
import sys
import zipfile
import urllib.request


RMLIB_URL = "https://github.com/roosterMAP/rmlib/archive/refs/heads/main.zip"
RMLIB_DIR = os.path.join(bpy.utils.script_path_user(), "modules", "rmlib")
RMLIB = False

class RMLIB_OT_RestartPrompt(bpy.types.Operator):
	"""Prompt the user to restart Blender"""
	bl_idname = "rmlib.restart_prompt"
	bl_label = "Restart Blender"

	def execute(self, context):
		self.report({'INFO'}, "Please restart Blender to complete the installation.")
		return {'FINISHED'}

	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_props_dialog(self)

	def draw(self, context):
		layout = self.layout
		layout.label(text="rmlib has been installed successfully.")
		layout.label(text="Please restart Blender to complete the installation.")

class RMLIB_OT_DownloadPrompt(bpy.types.Operator):
	"""Prompt to download rmlib"""
	bl_idname = "rmlib.download_prompt"
	bl_label = "Download rmlib"

	def download_rmlib(self):
		try:
			# define paths
			zip_path = os.path.join(bpy.utils.script_path_user(), "rmlib.zip")
			modules_dir = os.path.join(bpy.utils.script_path_user(), "modules")
			extracted_dir = os.path.join(modules_dir, "rmlib-main")
			target_dir = os.path.join(modules_dir, "rmlib")

			# Ensure the modules directory exists
			os.makedirs(modules_dir, exist_ok=True)

			# Download the zip file
			with urllib.request.urlopen(RMLIB_URL, timeout=10.0) as response, open(zip_path, 'wb') as out_file:
				out_file.write(response.read())

			# Extract the zip file
			with zipfile.ZipFile(zip_path, 'r') as zip_ref:
				zip_ref.extractall(modules_dir)

			# Rename the extracted folder to "rmlib"
			if os.path.exists(extracted_dir):
				if os.path.exists(target_dir):
					# Remove the old "rmlib" folder if it exists
					import shutil
					shutil.rmtree(target_dir)
				os.rename(extracted_dir, target_dir)

			# Clean up the zip file
			os.remove(zip_path)

			# Mark progress as complete
			return True

		except Exception as e:
			return False

	def invoke(self, context, event):
		return context.window_manager.invoke_confirm(self, event)

	def execute(self, context):
		if self.download_rmlib():
			self.report({'INFO'}, "rmlib successfully downloaded and installed.")
			bpy.ops.rmlib.restart_prompt('INVOKE_DEFAULT')
			return { 'FINISHED' }
		self.report({'ERROR'}, "Failed to download rmlib.")
		return { 'CANCELLED' }


class rmKitUVPannel_parent( bpy.types.Panel ):
	bl_idname = "VIEW3D_PT_RMKITUV_PARENT"
	bl_label = "rmUV"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "rmUV"

	def draw( self, context ):
		layout = self.layout
		rmlib_exists = os.path.exists(RMLIB_DIR) #Check if rmlib exists
		button_label = "Update rmlib" if rmlib_exists else "Download rmlib" #Set the button label dynamically
		layout.operator("rmlib.download_prompt", text=button_label) #Add the button with the dynamic label


class rmKitUVPannel_parent_uv( bpy.types.Panel ):
	bl_idname = "UV_PT_RMKITUV_PARENT"
	bl_label = "rmUV"
	bl_space_type = "IMAGE_EDITOR"
	bl_region_type = "UI"
	bl_category = "rmUV"

	def draw( self, context ):
		layout = self.layout


def operator_exists(idname):
	names = idname.split(".")
	a = bpy.ops
	for prop in names:
		a = getattr(a, prop)
		
	try:
		name = a.__repr__()
	except Exception as e:
		print(e)
		return False

	return True


def register():
	if not operator_exists( RMLIB_OT_RestartPrompt.bl_idname ):
		bpy.utils.register_class(RMLIB_OT_RestartPrompt)
	if not operator_exists( RMLIB_OT_DownloadPrompt.bl_idname ):	
		bpy.utils.register_class(RMLIB_OT_DownloadPrompt)

	bpy.utils.register_class( rmKitUVPannel_parent )

	global RMLIB
	RMLIB = os.path.exists( RMLIB_DIR )
	if RMLIB_DIR not in sys.path:
		sys.path.append(RMLIB_DIR)
	if not RMLIB:
		return

	from . import (
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
	)

	bpy.utils.register_class( rmKitUVPannel_parent_uv )
	loopringuv.register()
	move_to_furthest_uv.register()
	linear_deformer_uv.register()
	panel.register()
	stitch.register()
	gridify.register()
	relativeislands.register()
	unrotate.register()
	uvtransform.register()
	rectangularize.register()
	hotspot.register()
	uvboundstransform.register()
	uvgrowshrink.register()	
	preferences.register()

def unregister():
	if operator_exists( RMLIB_OT_RestartPrompt.bl_idname ):
		bpy.utils.unregister_class(RMLIB_OT_RestartPrompt)
	if operator_exists( RMLIB_OT_DownloadPrompt.bl_idname ):
		bpy.utils.unregister_class(RMLIB_OT_DownloadPrompt)

	bpy.utils.unregister_class(rmKitUVPannel_parent)
	
	global RMLIB
	if not RMLIB:
		return

	bpy.utils.unregister_class( rmKitUVPannel_parent_uv )
	loopringuv.unregister()
	move_to_furthest_uv.unregister()
	linear_deformer_uv.unregister()
	panel.unregister()
	stitch.unregister()
	gridify.unregister()
	relativeislands.unregister()
	unrotate.unregister()
	uvtransform.unregister()
	rectangularize.unregister()
	hotspot.unregister()
	uvboundstransform.unregister()
	uvgrowshrink.runegister()	
	preferences.unregister()