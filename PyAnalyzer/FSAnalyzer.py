from __future__ import division
import os
import math
import copy
from PIL import Image
from struct import unpack

inputDir = 'Input'
midputDir = 'Midput'
outputDir = 'Output'
scaleSize = 500000000
widthPreference = 0
heightPreference = 0
maxPreference = -25
minPreference = -50
mixMode = 'average'
MIX_MODES = ['max', 'average']
openMidput = True
openOutput = True

lookupTable = [(i-128)/128 for i in range(128,256)]
lookupTable.extend([(i-128)/128 for i in range(128)])

print 'Getting the txt files in "' + inputDir +'" for input frame shots...'
for files in os.listdir(inputDir):
    path = os.path.join(inputDir, files)
    if not os.path.isdir(path):
        if files[files.rfind('.'):] == '.txt':
            # Only operate on txt file
            print 'Operating on ' + path
            ampQue = []
            try:
                inData = open(path, 'r')
                line = inData.readline().split()
                startF = int(line[0])
                endF = int(line[1])
                sRate = int(line[2])
                fSize = int(line[3])

                # Preparation for FFT
                n = fSize // 2
                m = int(math.log(n) / math.log(2))
                if n != (1<<m) or n*2!=fSize:
                    print "Error: size for each sample should be power of 2"
                    continue
                cos = [math.cos(-2*math.pi*i/n) for i in xrange(n//2)]
                sin = [math.sin(-2*math.pi*i/n) for i in xrange(n//2)]
                window = [(0.42 - 0.5*math.cos(2*math.pi*i/(n-1)) + 0.08*math.cos(4*math.pi*i/(n-1))) for i in xrange(n)]
                frequency = startF
                fsFragment = []
                windowType = 1
                # Operate on each window
                while True:
                    packet = inData.read(fSize)
                    if (len(packet) < fSize):
                        break
                    re = [window[i] * lookupTable[ord(packet[2*i])] for i in xrange(n)]
                    im = [window[i] * lookupTable[ord(packet[2*i+1])] for i in xrange(n)]

                    # FFT extract from the Android project
                    j = 0
                    n2 = n//2
                    for i in xrange(n-1):
                        n1 = n2
                        while (j >= n1):
                            j -= n1
                            n1 = n1 // 2
                        j += n1
                        if (i < j):
                            re[i], re[j] = re[j], re[i]
                            im[i], im[j] = im[j], im[i]
                    n2 = 1
                    for i in xrange(m):
                        n1 = n2
                        n2 *= 2
                        a = 0
                        for j in xrange(n1):
                            c = cos[a]
                            s = sin[a]
                            a += 1<<(m-i-1)
                            for k in xrange(j, n, n2):
                                kn = k + n1
                                t1 = c*re[kn] - s*im[kn]
                                t2 = s*re[kn] + c*im[kn]
                                re[kn] = re[k] - t1
                                im[kn] = im[k] - t2
                                re[k] += t1
                                im[k] += t2
                    mag = [0 for i in xrange(n)]
                    for i in xrange(n):
                        targetIndex = (i+n//2) % n
                        realPower = re[i] / n
                        realPower *= realPower
                        imagPower = im[i] / n
                        imagPower *= imagPower
                        mag[targetIndex] = 10*math.log10(math.sqrt(realPower + imagPower))

                    # Cut the DC part and use only the valid part
                    startP = 0
                    if frequency - sRate / 2 < startF:
                        startP = int(math.floor(startF - frequency + sRate/2) * n / sRate)
                    if windowType == 1:
                        endP = n // 3
                        if frequency - sRate / 6 > endF:
                            endP = n // 3 - int(math.floor(frequency - sRate/6 - endF) * n / sRate)
                        fsFragment = mag[n*2//3: n]
                        frequency += sRate //3
                    else:
                        endP = n
                        if frequency + sRate / 2 > endF:
                            endP = n - int(math.floor(frequency + sRate/2 - endF) * n / sRate)
                        mag[n*2//3 - n//3: n - n//3] = fsFragment[:]
                        frequency += sRate
                    if startP < endP:
                        ampQue.extend(mag[startP:endP])
                    windowType = 3-windowType

            except IOError as e:
                print 'Error happen in reading file: {0}. {1}'.format(e.errno, e.strerror)
                continue
            except AttributeError as e:
                print 'File format error: {0}. {1}'.format(e.errno, e.strerror)
                continue
            except EOFError:
                pass

            print 'File reading succeeded',
            if openMidput:
                try:
                    print ', Generating Mid output...'
                    if not os.path.exists(midputDir):
                        os.makedirs(midputDir)
                    midputName = '{0}.txt'.format(files[:files.rfind('.')])
                    midPath = os.path.join(midputDir, midputName)
                    midF = open(midPath, 'w')
                    midF.write('{0} {1}\n'.format(startF, endF))
                    for ind, i in enumerate(ampQue):
                        midF.write('{0}'.format(i))
                        if (ind % 1000 == 0):
                            midF.write('\n')
                        else:
                            midF.write(',')
                    midF.close()
                    print 'Generating succeeded',
                except IOError as e:
                    print 'Error in output image: {0}. {1}'.format(e.errno, e.strerror),


            if not openOutput:
                continue
            print ', Generating image...'
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
            if (hScale == 0):
                print "Error: min amplitude is equal to max amplitude"
                continue
            prevFreq = startF - 1
            for ind, hgt in enumerate(colQue):
                hgt = min(int((hgt - minA) // hScale), height)
                for i in range(hgt):
                    pixels[ind, i] = (100, 100, 100)

                # Display the scale
                freq = int(math.floor(ind * (endF - startF) / width + 0.5)) + startF
                if (freq // scaleSize != prevFreq // scaleSize):
                    for i in range(int(height // 20)):
                        if (pixels[ind, i] == (100, 100, 100)):
                            pixels[ind, i] = (255, 255, 255)
                        else:
                            pixels[ind, i] = (0, 0, 0)
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
