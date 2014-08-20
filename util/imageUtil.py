# coding: latin-1

'''
Created on Mar 21, 2013

@author: hifly
'''

import StringIO
import urllib
from PIL import Image
from gi.repository import GdkPixbuf
from constant import constantsAccessor as K


def fromImageToPixbuf(y):
    if y.mode != K.ImageConstants.RGB_SHORT_NAME:
        y = y.convert(K.ImageConstants.RGB_SHORT_NAME)
    buff = StringIO.StringIO()
    y.save(buff, 'ppm')
    contents = buff.getvalue()
    buff.close()
    loader = GdkPixbuf.PixbufLoader.new_with_type('pnm')
    loader.write(contents)
    pixbuf = loader.get_pixbuf()
    loader.close()
    return pixbuf

def fromPixbufToPilImage(pixbuf):
    width,height = pixbuf.get_width(),pixbuf.get_height()
    y = Image.fromstring(K.ImageConstants.RGB_SHORT_NAME,(width,height),pixbuf.get_pixels() )
    return y

def savePhotoFromUrl(url,filename):
    f = open( filename, 'wb' )
    data = urllib.urlopen(url).read()
    f.write( data )
    f.close()

def savePhotoFromPixbuf(pixbuf,type,quality,filename):
    pixbuf.savev(filename, type, [],[])

