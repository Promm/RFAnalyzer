from __future__ import division
import os
import math
from PIL import Image

inputDir = 'Input'
outputDir = 'Output'
scaleSize = 500000000
widthPreference = 0
heightPreference = 0
maxPreference = None
minPreference = None
mixMode = 'average'
MIX_MODES = ['max', 'average']

print 'Getting the txt files in "' + inputDir +'" for input frame shots...'
for files in os.listdir(inputDir):
    path = os.path.join(inputDir, files)
    if not os.path.isdir(path):
        if files[files.rfind('.'):] == '.txt':
            # Only operate on txt file
            print 'Operating on ' + path
            startF = 0
            endF = 0
            ampQue = []
            try:
                inData = open(path, 'r')
                for i, line in enumerate(inData):
                    # Operate on the input file
                    if i == 0:
                        # First line includes frequency info
                        line = line.split()
                        startF = int(line[0])
                        endF = int(line[1])
                    else:
                        # Following lines include amplitude info
                        line = line.split(',')
                        ampQue.extend([float(element) for element in line])
            except IOError as e:
                print 'Error happen in reading file: {0}. {1}'.format(e.errno, e.strerror)
                continue
            except AttributeError as e:
                print 'File format error: {0}. {1}'.format(e.errno, e.strerror)
                continue

            print 'File reading succeeded, Generating image...'
            height = 600
            width = int(math.floor((endF - startF) / 1000000 + 0.5)) # Round
            if heightPreference != 0:
                height = heightPreference
            if widthPreference != 0:
                width = widthPreference
            wScale = len(ampQue) / width

            sumCol = 0
            countCol = 0
            prevCol = 0
            colQue = []
            for ind, element in enumerate(ampQue):
                col = ind // wScale
                if (col == prevCol): # Still in the same column
                    countCol += 1
                    if (mixMode == MIX_MODES[0]): # Max
                        sumCol = max(element, sumCol)
                    else: # Average
                        sumCol += element
                else: # Column changed, get the value for the previous column
                    colHeight = 0
                    if (mixMode == MIX_MODES[0]): #Max
                        colHeight = sumCol
                    else: # Average
                        colHeight = sumCol / countCol
                    colQue.append(colHeight)
                    countCol = 1
                    sumCol = element
                prevCol = col

            # Generate the image
            imgOut = Image.new('RGB', (width, height), "black")
            pixels = imgOut.load()
            maxA = max(colQue)
            minA = min(colQue)
            if maxPreference is not None:
                maxA = maxPreference
            if minPreference is not None:
                minA = minPreference
            hScale = (maxA - minA) / height
            prevFreq = startF - 1
            for ind, hgt in enumerate(colQue):
                hgt = int((hgt - minA) // hScale)
                for i in range(hgt):
                    pixels[ind, i] = (255, 0, 0)

                # Display the scale
                freq = int(math.floor(ind * (endF - startF) / width + 0.5)) + startF
                if (freq // scaleSize != prevFreq // scaleSize):
                    for i in range(int(height // 20)):
                        if (pixels[ind, i] == (255, 0, 0)):
                            pixels[ind, i] = (255, 255, 255)
                        else:
                            pixels[ind, i] = (0, 255, 255)
                prevFreq = freq
            imgOut = imgOut.transpose(Image.FLIP_TOP_BOTTOM)

            try:
                # Create output dir if not exists
                if not os.path.exists(outputDir):
                    os.makedirs(outputDir)

                # Output image
                outputName = '{0}.png'.format(files[:files.rfind('.')])
                outPath = os.path.join(outputDir, outputName)
                imgOut.save(outPath)
                print 'Operation succeeded! Image output to ' + outPath
            except IOError as e:
                print 'Error in output image: {0}. {1}'.format(e.errno, e.strerror)
