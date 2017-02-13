#-------------------------------------------------------------------------------
# Produce random files
#-------------------------------------------------------------------------------
#from PIL import Image
import numpy
import uuid
import array
import os

import random, tempfile

word_list = []

#-------------------------------------------------------------------------------
# Reads the word list to use for the 'readable' text tests
#-------------------------------------------------------------------------------
def load_word_list():
    # Word list from FreeBSD Dict
    f = open("wordlist", "r")
    for line in f:
        word_list.append(line.strip())
    return


'''
# TODO:
#   - This is by now not supported as PIL (pillow) package is required to produce output and may not be available locally
#-------------------------------------------------------------------------------
# Create a valid but random image (jpeg or png)
#-------------------------------------------------------------------------------
def get_image(size, extension):
    fsize = 0
    fname = os.path.join(tempfile.gettempdir(), \
        '%s.%s' % (str(uuid.uuid4()), extension))

    # This will give a max JPEG of few mega
    x_max = 3500
    x_min = 0

    while x_max >= x_min:
        # Mid of the interval
        x = 1.0 * (x_max + x_min) / 2

        # save the image
        a = numpy.random.rand(x,x,3) * 255
        image_out = Image.fromarray(a.astype('uint8')).convert('RGBA')
        image_out.save(fname)
        fsize = os.path.getsize(fname)

        # lets go on binary search for the size
        diff = (1.0 * (fsize - size)/ size)
        if abs(diff) > 0.01 and diff > 0:
            x_max = x
        elif abs(diff) > 0.01 and diff < 0:
            x_min = x
        elif x_max - x_min <= 2.0:
            break
        else:
            break
            # got it!
    return fname
'''


#-------------------------------------------------------------------------------
# Produces a random text from the word_list given the size in bytes.
# Returns exactly this amount of bytes.
#-------------------------------------------------------------------------------
def get_text(size):
    t = ""
    while len(t) < size:
        t += random.choice(word_list)
        # We want to read the text :)
        if random.random() > 0.1:
            t +=  " "
        else:
            t += "\r\n"
    t = t[0:size]
    return t


#-------------------------------------------------------------------------------
# Produces a random bunch of bytes given the size in bytes
# Returns exactly this amount of bytes.
#-------------------------------------------------------------------------------
def get_binary(size):
    return bytearray(random.getrandbits(8) for i in range(size))



#-------------------------------------------------------------------------------
# Generic wrapper for file generation
# Prepares the file for the test given size and the file type
#
# File types:
#    1. Random bytes
#    2. Random text
#    3. JPEG image (extension, magic numbers, random pixels)
#    4. Fake JPEG image (extension, magic numbers, plain text) 
#-------------------------------------------------------------------------------
def make_file(size, file_type):
    if file_type == 1:
        # put random data in the file -- call it a gzip
        rand_bytes = bytearray(random.getrandbits(8) for i in range(size-2))
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".gz")
        fname = tfile.name
        tfile.write(array.array('B', "1f8b".decode("hex")))
        tfile.write(rand_bytes)
        tfile.close()
        return fname

    elif file_type == 2:
        # start-up the dictionary
        load_word_list()
        # put a readable text in the file
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        fname = tfile.name
        tfile.write(get_text(size))
        tfile.close()
        return fname

    elif file_type == 3:
        # put a valid jpeg image with random pixels
        return get_image(size, "jpeg")

    elif file_type == 4:
        # create a file with magic number of jpeg, jpeg extension,
        # but only normal text afterward
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg")
        fname = tfile.name
        tfile.write(array.array('B', "ffd8ffe0".decode("hex")))
        tfile.write(get_text(size-4))
        tfile.close()
        return fname

