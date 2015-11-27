from __future__ import division
import os
import math
import copy
import datetime
from PIL import Image, ImageFont, ImageDraw
from struct import unpack

inputDir = 'Input'
midputDir = 'Midput'
outputDir = 'Output'
arffDir = 'Arff'
scaleSize = 500000000
sScaleSize = 100000000
markScale = 1000000000
widthPreference = 0
heightPreference = 0
maxPreference = -25
minPreference = -45
mixMode = 'average'
MIX_MODES = ['max', 'average']
openMidput = False
openReadFromMid = False
openOutput = False

openArff = True
appendArff = True
arffStep = 2000000
arffFile = 'ArffOut.arff'
mapFile = 'ArffMap.arff'
freqs = []
attrFreqs = []
locArray = []
ampArray = []


lookupTable = [(i-128)/128 for i in range(128,256)]
lookupTable.extend([(i-128)/128 for i in range(128)])

readDir = inputDir
if openReadFromMid:
    readDir = midputDir
print 'Getting the txt files in "' + inputDir +'" for input frame shots...'
for files in os.listdir(readDir):
    path = os.path.join(readDir, files)
    if not os.path.isdir(path):
        try:
            if not openReadFromMid and files[files.rfind('.'):] == '.iq':
                # Open target raw data
                print 'Operating on ' + path
                ampQue = []
                inData = open(path, 'r')
                line = inData.readline().split()
                startF = int(line[0])
                endF = int(line[1])
                startO = startF
                endO = endF
                sRate = int(line[2])
                fSize = int(line[3])
                loct = line[4]
                latit = float(line[5])
                longit = float(line[6])
                altit = float(line[7])

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
                    for i in xrange(1,n-1):
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
                        if realPower + imagPower == 0:
                        # Set small default value
                            realPower = 1e-12
                        mag[targetIndex] = 10*math.log10(math.sqrt(realPower + imagPower))

                    # Cut the DC part and use only the valid part
                    startP = 0
                    if frequency - sRate / 2 < startF:
                        startP = int(math.floor(startF - frequency + sRate/2) * n / sRate)
                        startO = frequency - sRate / 2 + sRate * startP / n
                    if windowType == 1:
                        endP = n // 3
                        if frequency - sRate / 6 > endF:
                            endP = n // 3 - int(math.floor(frequency - sRate/6 - endF) * n / sRate)
                            endO = frequency - sRate / 2 + sRate * endP / n
                        fsFragment = mag[n*2//3: n]
                        frequency += sRate //3
                    else:
                        endP = n
                        if frequency + sRate / 2 > endF:
                            endP = n - int(math.floor(frequency + sRate/2 - endF) * n / sRate)
                            endO = frequency - sRate / 2 + sRate * endP / n
                        mag[n*2//3 - n//3: n - n//3] = fsFragment[:]
                        frequency += sRate
                    if startP < endP:
                        ampQue.extend(mag[startP:endP])
                    windowType = 3-windowType

            elif openReadFromMid and files[files.rfind('.'):] == '.txt':
                # Operate on mid txt file
                print 'Operating on ' + path
                startF = 0
                endF = 0
                startO = 0
                endO = 0
                loct = 0
                latit = 0
                longit = 0
                altit = 0
                ampQue = []
                inData = open(path, 'r')
                for i, line in enumerate(inData):
                    # Operate on the input file
                    if i == 0:
                        # First line includes frequency info
                        line = line.split()
                        startF = int(line[0])
                        endF = int(line[1])
                        startO = float(line[2])
                        endO = float(line[3])
                        loct = line[4]
                        latit = float(line[5])
                        longit = float(line[6])
                        altit = float(line[7])
                    else:
                        # Following lines include amplitude info
                        line = line.split(',')
                        if (line[-1] == ''):
                            line = line[:-1]
                        ampQue.extend([float(element) for element in line])
            else:
                continue

            if (openArff):
                if (freqs == []):
                    queLen = len(ampQue)
                    freqs = [(startO + (endO-startO) * i / (queLen-1)) for i in xrange(queLen)]
                    pFreq = freqs[0]
                    attrFreqs.append(pFreq)
                    for i in freqs:
                        if (i >= pFreq + arffStep):
                            pFreq = i
                            attrFreqs.append(pFreq)
                if (len(ampQue) != len(freqs)):
                    print 'Data number dismatch, this data will not be output into arff'
                else:
                    pAmp = []
                    ampS = 0
                    pFreq = freqs[0]
                    cFreq = 0
                    for index, i in enumerate(ampQue):
                        if (freqs[index] >= pFreq + arffStep):
                            pFreq = freqs[index]
                            if (cFreq == 0):
                                pAmp.append(0)
                            else:
                                pAmp.append(ampS / cFreq)
                            ampS = i
                            cFreq = 1
                        else:
                            ampS += i
                            cFreq += 1
                    if (cFreq == 0):
                        pAmp.append(0)
                    else:
                        pAmp.append(ampS / cFreq)
                    ampArray.append(pAmp)
                    pTime = files[files.find('_')+1 :files.rfind('.')]
                    if (len(pTime) < 14):
                        pTime = '00000000000000'
                    elif (len(pTime) > 14):
                        pTime = pTime[:15]
                    locArray.append([pTime, loct, latit, longit, altit])

        except IOError as e:
            print 'Error happen in reading file: {0}. {1}'.format(e.errno, e.strerror)
            continue
        except AttributeError as e:
            print 'File format error: {0}. {1}'.format(e.errno, e.strerror)
            continue
        except EOFError:
            pass

        print 'File reading succeeded',
        try:
            if openMidput and not openReadFromMid:
                print ', Generating Mid output...'
                if not os.path.exists(midputDir):
                    os.makedirs(midputDir)
                midputName = '{0}.txt'.format(files[:files.rfind('.')])
                midPath = os.path.join(midputDir, midputName)
                midF = open(midPath, 'w')
                midF.write('{0} {1} {2} {3} {4} {5} {6} {7}\n'.format(startF,
                        endF, startO, endO, loct, latit, longit, altit))
                for ind, i in enumerate(ampQue):
                    midF.write('{0}'.format(i))
                    if (ind % 1000 == 999):
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


try:
    if (openArff and len(ampArray) > 0):
        print 'Outputing Arff file'
        if not os.path.exists(arffDir):
            os.makedirs(arffDir)
        arffPath = os.path.join(arffDir, arffFile)
        if (appendArff and os.path.isfile(arffPath)):
            arffF = open(arffPath, 'a')
        else:
            arffF = open(arffPath, 'w')
            arffF.write('@RELATION FrameshotWirelessWaves\n')
            arffF.write('@ATTRIBUTE timestamp DATE "yyyyMMddHHmmss"\n')
            arffF.write('@ATTRIBUTE location STRING\n')
            arffF.write('@ATTRIBUTE latitude NUMERIC\n')
            arffF.write('@ATTRIBUTE longitude NUMERIC\n')
            arffF.write('@ATTRIBUTE altitude NUMERIC\n')

            arffM = open(os.path.join(arffDir, mapFile), 'w')
            arffM.write('@RELATION IDvsFREQ\n')
            arffM.write('@ATTRIBUTE id NUMERIC\n')
            arffM.write('@ATTRIBUTE freq NUMERIC\n')
            arffM.write('\n@DATA\n')

            for ind, i in enumerate(attrFreqs):
                arffF.write('@ATTRIBUTE {0} NUMERIC\n'.format(ind))
                arffM.write('{0}, {1}\n'.format(ind, i))
            arffF.write('\n@DATA\n')
            arffM.close()
        for ind, i in enumerate(ampArray):
            arffF.write('{0}, {1}, {2}, {3}, {4}'.format(locArray[ind][0],
                    locArray[ind][1], locArray[ind][2], locArray[ind][3], locArray[ind][4]))
            for j in i:
                arffF.write(', {0}'.format(abs(j)))
            arffF.write('\n')
        arffF.close()
        print 'Output succeeded'
except IOError as e:
    print 'Error in output arff: {0}. {1}'.format(e.errno, e.strerror)
