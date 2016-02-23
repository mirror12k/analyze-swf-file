#!/usr/bin/env python3


import sys
import os
import math

import tempfile

import zlib
import lzma
import struct
import bitstruct



# a swf file unpacker and analyzer
# majority of information taken from https://www.adobe.com/devnet/swf.html (version 19)
# some additional information taken from https://github.com/claus/as3swf/wiki/SWF-tag-support-chart



class SWFFileUnpackingException(Exception):
	'''generic exception during unpacking of a swf file typically due to incorrect structure or unexpected values'''

class SWFRect(object):
	def __init__(self, xmin, xmax, ymin, ymax):
		self.xmin = xmin
		self.xmax = xmax
		self.ymin = ymin
		self.ymax = ymax
	def __str__(self):
		return 'SWFRect('+str(self.xmin)+','+str(self.xmax)+','+str(self.ymin)+','+str(self.ymax)+')'


tagCodeTranslation = {
	0:'End',
	1:'ShowFrame',
	2:'DefineShape',
	4:'PlaceObject',
	5:'RemoveObject',
	6:'DefineBits',
	7:'DefineButton',
	8:'JPEGTables',
	9:'SetBackgroundColor',
	10:'DefineFont',
	11:'DefineText',
	12:'DoAction',
	13:'DefineFontInfo',
	14:'DefineSound',
	15:'StartSound',
	17:'DefineButtonSound',
	18:'SoundStreamHead',
	19:'SoundStreamBlock',
	20:'DefineBitsLossless',
	21:'DefineBitsJPEG2',
	22:'DefineShape2',
	23:'DefineButtonCxform',
	24:'Protect',
	26:'PlaceObject2',
	28:'RemoveObject2',
	32:'DefineShape3',
	33:'DefineText2',
	34:'DefineButton2',
	35:'DefineBitsJPEG3',
	36:'DefineBitsLossless2',
	37:'DefineEditText',
	39:'DefineSprite',
	41:'ProductInfo', # taken from https://github.com/claus/as3swf/wiki/SWF-tag-support-chart
	43:'FrameLabel',
	45:'SoundStreamHead2',
	46:'DefineMorphShape',
	48:'DefineFont2',
	56:'ExportAssets',
	57:'ImportAssets',
	58:'EnableDebugger',
	59:'DoInitAction',
	60:'DefineVideoStream',
	61:'VideoFrame',
	62:'DefineFontInfo2',
	63:'DebugID', # taken from https://github.com/claus/as3swf/wiki/SWF-tag-support-chart
	64:'EnableDebugger2',
	65:'ScriptLimits',
	66:'SetTabIndex',
	69:'FileAttributes',
	70:'PlaceObject3',
	71:'ImportAssets2',
	73:'DefineFontAlignZones',
	74:'CSMTextSettings',
	75:'DefineFont3',
	76:'SymbolClass',
	77:'Metadata',
	78:'DefineScalingGrid',
	82:'DoABC',
	83:'DefineShape4',
	84:'DefineMorphShape2',
	86:'DefineSceneAndFrameLabelData',
	87:'DefineBinaryData',
	88:'DefineFontName',
	89:'StartSound2',
	90:'DefineBitsJPEG4',
	91:'DefineFont4',
	93:'EnableTelemetry',
}


class SWFTag(object):
	def __init__(self, code, length):
		self.code = code
		self.length = length

		self.typeName = tagCodeTranslation.get(self.code, '!UNKNOWN!')
		if self.typeName == '!UNKNOWN!':
			print('warning: unknown swf tag code: '+str(self.code))
	def isEndTag(self):
		return self.typeName == 'End'
	def __str__(self):
		return 'SWFTag(code='+str(self.code)+' "'+self.typeName+'", length='+str(self.length)+')'


class SWFFile(object):
	def __init__(self, filepath):
		self.filepath = filepath

		self.compression = None
		self.version = None
		self.fileLength = None
		self.frameSize = None
		self.frameRate = None
		self.frameCount = None

		self.tags = []

		self.chunkSize = 16 * 4096

		self.load()

	def load(self):
		'''loads the swf file at the filepath'''
		self.handle = open(self.filepath, 'rb')

		self.unpackHeader1()
		print('signature:', self.signature)
		print('version:', self.version)
		print('fileLength:', self.fileLength)

		if self.compression != 'none':
			self.decompress()

		self.unpackHeader2()

		print('frameSize:', self.frameSize)
		print('frameRate:', self.frameRate)
		print('frameCount:', self.frameCount)

		self.unpackTags()
		for tag in self.tags:
			print(tag)
			if tag.typeName == '!UNKNOWN!':
				print('warning: unknown tag!')


	def decompress(self):
		'''replaces the handle with a tempfile handle with all content decompressed'''
		temp = tempfile.TemporaryFile('w+b')
		if self.compression == 'zlib':
			decompressor = zlib.decompressobj()
		elif self.compression == 'lzma':
			decompressor = lzma.LZMADecompressor()
		else:
			raise Exception("unknown compression algorithm: "+self.compression)
		chunk = self.handle.read(self.chunkSize)
		while len(chunk) > 0:
			temp.write(decompressor.decompress(chunk))
			chunk = self.handle.read(self.chunkSize)
		temp.seek(0)
		self.handle = temp

	def unpackHeader1(self):
		'''unpacks the first 8 bytes of the header and figures out what compression there is'''
		header = self.handle.read(8)
		signature, self.version, self.fileLength = struct.unpack('<3sBI', header)

		signature = signature.decode('ascii')
		if signature == 'FWS':
			self.compression = 'none'
		elif signature == 'CWS':
			self.compression = 'zlib'
		elif signature == 'ZWS':
			self.compression = 'lzma'
		else:
			raise SWFFileUnpackingException('unknown file signature: "'+signature+'"')

		self.signature = signature

	def unpackHeader2(self):
		'''unpacks the rest of the header data that might have been compressed'''
		self.frameSize = self.unpackRect()
		self.frameRate, self.frameCount = struct.unpack('<HH', self.handle.read(4))
		# frameRate is an 8.8 float actually, but i'm not sure how to unpack that...

	def unpackRect(self):
		data = self.handle.read(1)
		size, = bitstruct.unpack('u5', data)
		data += self.handle.read(math.ceil((size * 4 - 3) / 8))
		xmin, xmax, ymin, ymax = bitstruct.unpack('p5'+('s'+str(size))*4, data)
		return SWFRect(xmin, xmax, ymin, ymax)

	def unpackTags(self):
		sample = self.handle.read(2)
		tag = None
		while len(sample) > 0:
			if tag is not None and tag.isEndTag():
				print('warning: swf has tags after an end tag!')
			self.handle.seek(-2, os.SEEK_CUR)
			tag = self.unpackTag()
			self.tags.append(tag)

			sample = self.handle.read(2)

	def unpackTag(self):
		tag = self.unpackTagHeader()
		self.handle.read(tag.length)
		return tag
	def unpackTagHeader(self):
		data, = struct.unpack('<H', self.handle.read(2))
		tagCode = data >> 6
		tagLength = data & 0x3f
		if tagLength == 0x3f:
			tagLength, = struct.unpack('<I', self.handle.read(4))
		return SWFTag(tagCode, tagLength)




def main():
	if len(sys.argv) < 2:
		print('filepath required')
	else:
		file = SWFFile(sys.argv[1])


if __name__ == '__main__':
	main()
