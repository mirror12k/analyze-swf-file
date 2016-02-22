#!/usr/bin/env python3


import sys
import tempfile
import zlib
import lzma
from struct import unpack


class SWFFileUnpackingException(Exception):
	'''generic exception during unpacking of a swf file typically due to incorrect structure or unexpected values'''

class SWFFile(object):
	def __init__(self, filepath):
		self.filepath = filepath

		self.compression = None
		self.version = None
		self.fullLength = None

		self.chunkSize = 16 * 4096

		self.load()
	def load(self):
		'''loads the swf file at the filepath'''
		self.handle = open(self.filepath, 'rb')
		header = self.handle.read(8)
		signature, version, filelength = unpack('<3sBI', header)

		signature = signature.decode('ascii')
		if signature == 'FWS':
			self.compression = 'none'
		elif signature == 'CWS':
			self.compression = 'zlib'
		elif signature == 'ZWS':
			self.compression = 'lzma'
		else:
			raise SWFFileUnpackingException('unknown file signature: "'+signature+'"')

		self.version = version
		self.fullLength = filelength

		print('signature: ', signature)
		print('version: ', version)
		print('filelength: ', filelength)

		if self.compression != 'none':
			self.decompress()

		with open('dump', 'wb') as f:
			f.write(self.handle.read())
		# print(self.handle.read())

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




def main():
	if len(sys.argv) < 2:
		print('filepath required')
	else:
		file = SWFFile(sys.argv[1])


if __name__ == '__main__':
	main()
