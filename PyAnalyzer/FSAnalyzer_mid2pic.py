from __future__ import division
import os
import math
from PIL import Image, ImageFont, ImageDraw

inputDir = 'Midput'
outputDir = 'Output'
scaleSize = 500000000
sScaleSize = 100000000
markScale = 1000000000
widthPreference = 0
heightPreference = 0
maxPreference = -25
minPreference = -45
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
                        if (line[-1] == ''):
                            line = line[:-1]
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
            imgOut = Image.new('RGB', (width, height), "white")
            pixels = imgOut.load()
            maxA = max(colQue)
            minA = min(colQue)
            if maxPreference is not None:
                maxA = maxPreference
            if minPreference is not None:
                minA = minPreference
            print "Amplitude changes from {0} to {1}".format(minA, maxA)
            hScale = (maxA - minA) / height
            prevFreq = startF - 1
            scaleArray = []
            for ind, hgt in enumerate(colQue):
                hgt = min(int((hgt - minA) // hScale), height)
                for i in range(hgt):
                    pixels[ind, i] = (100, 100, 100)

                # Display the scale
                freq = int(math.floor(ind * (endF - startF) / width + 0.5)) + startF
                if (freq // scaleSize != prevFreq // scaleSize):
                    for i in range(int(height // 10)):
                        if (pixels[ind, i] == (100, 100, 100)):
                            pixels[ind, i] = (255, 255, 255)
                        else:
                            pixels[ind, i] = (0, 0, 0)
                    scaleArray.append([ind, freq, 0])
                elif (freq // sScaleSize != prevFreq // sScaleSize):
                    for i in range(int(height // 25)):
                        if (pixels[ind, i] == (100, 100, 100)):
                            pixels[ind, i] = (255, 255, 255)
                        else:
                            pixels[ind, i] = (0, 0, 0)
                    scaleArray.append([ind, freq, 1])
                prevFreq = freq
            imgOut = imgOut.transpose(Image.FLIP_TOP_BOTTOM)

            # Add Text
            d = ImageDraw.Draw(imgOut)
            fnt = ImageFont.load_default()
            textPos = [height * 8 // 9, height * 20 // 21]
            for i in scaleArray:
                d.text((i[0], textPos[i[2]]), "{0:.1f}".format(i[1]/markScale), font=fnt, fill=(255, 0, 0))

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
