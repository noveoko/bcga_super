import math
import os
import sys

bl_info = {
	"name": "BCGA",
	"author": "Vladimir Elistratov <vladimir.elistratov@gmail.com>",
	"version": (1, 0, 0),
	"blender": (2, 80, 0),
	"location": "View3D > Tool Shelf",
	"description": "BCGA: Computer Generated Architecture for Blender",
	"warning": "",
	"wiki_url": "https://github.com/vvoovv/bcga/wiki",
	"tracker_url": "https://github.com/vvoovv/bcga/issues",
	"support": "COMMUNITY",
	"category": "BCGA",
}


def register():
	from . import addon as _addon
	_addon.register()


def unregister():
	from . import addon as _addon
	_addon.unregister()
