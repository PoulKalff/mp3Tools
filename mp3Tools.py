#!C:\Program Files\Python27\pythonw.exe -u
import os, sys, array, time, inspect
from os import listdir, sep
from sys import argv
import argparse

# -- Static lists ------------------------------------------------------

accepted  = {'TIT2', 'TPE1', 'TALB', 'TRCK', 'TYER', 'APIC'}
transTable = {'TDRC': 'TYER', 'TT2': 'TIT2', 'TP1': 'TPE1', 'TAL': 'TALB', 'TRK': 'TRCK', 'TYE': 'TYER', 'PIC': 'APIC'}
romanNumbers = ['II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX']
smallWords = ['is', 'to', 'the', 'in', 'is', 'are', 'a', 'am', 'on', 'of', 'my', 'and', 'by', 'or', 'er', 'en', 'et', 'for', 'das', 'der', 'den']
casedWords = ['EP', 'LP', 'Demo', 'Single', 'ACDC', 'MOD', 'SOD', 'USA']
renameIllegal = ['/', '\\', ':', '*', '?', '"', '', '<', '>', '|']

# -- Class / Def -------------------------------------------------------

class PrintLog:
    """ Printer til skaerm og til en LOG-fil """

    def __init__(self):
        self.terminal = sys.stdout
        filename = inspect.getframeinfo(inspect.currentframe()).filename
        path = os.path.dirname(os.path.abspath(filename))
        self.log = open(os.path.join(path, time.strftime("%Y-%m-%d-%H-%M-%S.log")), 'w')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)  
        self.log.flush()

    def close(self, ):
        sys.stdout = self.terminal
        self.log.flush()
        self.log.close()


class Status:
    """ Helperclass to show status of a single file """

    def __init__(self, obj):
        self.parent = obj
        self.tagStatus = [0, 0, 0, 0]                   # Has V1? | Has Ape? | Has V2? | Has V23?
        self.frameStatus = [0, 0, 0, 0, 0, 0]           # Has Artist? | Has Title? | Has album? | Has Track? | Has Year | Has ANY illegal frame?
        self.pictureStatus = 0                          # Has internal Picture?
        self.update()

    def update(self):
        if len(self.parent.v1Data) > 0:     self.tagStatus[0] = 1
        else: self.tagStatus[0] = 0
        if len(self.parent.apeData) > 0:    self.tagStatus[1] = 1
        else: self.tagStatus[1] = 0
        if len(self.parent.frames) > 0:     self.tagStatus[2] = 1
        else: self.tagStatus[2] = 0
        if self.parent.version == 3:        self.tagStatus[3] = 1
        else: self.tagStatus[3] = 0

        if self.parent.frames.has_key('TPE1'):  self.frameStatus[0] = 1
        else: self.frameStatus[0] = 0
        if self.parent.frames.has_key('TIT2'):  self.frameStatus[1] = 1
        else: self.frameStatus[1] = 0
        if self.parent.frames.has_key('TALB'):  self.frameStatus[2] = 1
        else: self.frameStatus[2] = 0
        if self.parent.frames.has_key('TRCK'):  self.frameStatus[3] = 1
        else: self.frameStatus[3] = 0
        if self.parent.frames.has_key('TYER'):  self.frameStatus[4] = 1
        else: self.frameStatus[4] = 0
        self.frameStatus[5] = 0
        for frame in self.parent.frames.iterkeys():
            if frame not in accepted:
                self.frameStatus[5] = 1
                break

        if self.parent.frames.has_key('APIC'): self.pictureStatus = 1
        else: self.pictureStatus = 0


    def hasVitalFrames(self):
        if self.frameStatus[0] == 1 and self.frameStatus[1] == 1 and self.frameStatus[2] == 1: return True
        else: return False

    def getFullStatus(self):
        return '[' + ''.join(str(x) for x in self.tagStatus) + '-' + ''.join(str(x) for x in self.frameStatus) + '-' + str(int(self.pictureStatus)) + ']'

    def getTagStatus(self):
        return ''.join(str(x) for x in self.tagStatus)

    def getFramesStatus(self):
        return ''.join(str(x) for x in self.frameStatus)


class MP3Tag:

    def __init__(self, fil):
        self.path = fil
        self.fileName = os.path.basename(fil)[:-4]
        self.version = 0
        self.orgVersion = 0
        self.revision = 0
        self.flags = []
        self.tagSize = 0
        self.cleanedTagSize = 0
        self.frames = {}
        self.v1Data = []
        self.apeData = []
        fp = open(self.path, 'rb')
        self.fileCont = fp.read()
        fp.close()
        self._readTagV1()
        self._readApe()
        self._readTagV2()
        self.status = Status(self)


    def _getTrackFromName(self, name):
        """ Tries to get a track number from filename """
        parts = name.split()
        for part in parts:
            if len(part) < 3:
                try:
                    converted = int(part)
                    return converted
                except:
                    pass
        return False


    def _reverseHex(self, hexStr):
        """ Reverses a string """
        rev = ''
        for x in range(len(hexStr) - 1, -1, -1):
            rev += hexStr[x]
        return rev


    def _hexStringToChars(self, streng):
        """ Tager en HEX-encoded string og returnerer en liste af bytes """
        data = array.array('B')             #  array of bytes.
        for x in range(0, len(streng), 2):
            data.append(int(streng[x:x+2], 16))
        return data


    def _hexPad(self, string, length, rev=False):
        """ Fills HEX-string with zeroes to the required length """
        while len(string) < length:
            if rev:
                string = string + '0'
            else:
                string = '0' + string
        return string.upper()


    def _removeSyncSafe(self, streng):
        """ Removes the pattern FF00 used by ID3V24 """
        return streng.replace('ff00', 'ff')


    def _fixPicSignature(self, picData):
        """ Finds the beginning of Picture Data in frame and returns correct data frame signature """
        if 'FFD8FF' in picData[:50].upper():
            index = picData.upper().index('FFD8FF')           # signature for JPG
            return '696D6167652F6A7067000300' + picData[index:]
        elif '89504E' in picData[:50].upper():
            index = picData.upper().index('89504E')           # signature for PNG
            return '696D6167652F504E67000300' + picData[index:]
        return 'error'.encode('hex') # Return error if no picture signature found


    def _createHeader(self):
        """ Creating a new header, based on the current data, i.e. same as originial if no changes have been made """
        frames = []
        for key in self.frames.iterkeys():
            # Each frame is TAG(4) + LENGTH(4) + '000000'[3] + DATA[LENGTH - 1]
            fr_tag = key.encode('hex')
            fr_flags = '0000'         # Overwriting flags
            fr_encoding = '00'        # Overwriting encoding
            fr_data = ''
            for char in self.frames[key]:
                fr_data += char.encode('hex')
            if key == 'APIC':
                fr_data = self._fixPicSignature(fr_data)
            if self.orgVersion == 4:            # Only v4 sets syncsafe chars
                fr_data = self._removeSyncSafe(fr_data)
            fr_length = self._hexPad(hex(len(fr_encoding + fr_data) / 2)[2:], 8)
            # All 5 parts encoded to HEX
            enc_frame = self._hexStringToChars(fr_tag + fr_length + fr_flags + fr_encoding + fr_data)
            if fr_data != '6572726f72': # If fixpic fails
                frames.append(enc_frame)
        # Assembling Frames
        allFrames = array.array('B')
        for frame in frames:
            allFrames += frame
        # Creating ID3 header... ungracefull, but the best I can do :-S
        fs_8bit = self._hexPad(hex(len(allFrames))[2:].upper(), 8)
        fs_array = [self._hexPad(bin(int(fs_8bit[0:2], 16))[2:], 8),
                    self._hexPad(bin(int(fs_8bit[2:4], 16))[2:], 8),
                    self._hexPad(bin(int(fs_8bit[4:6], 16))[2:], 8),
                    self._hexPad(bin(int(fs_8bit[6:8], 16))[2:], 8)]
        bitString = ''.join(fs_array)
        fs_7bit = ['0' + bitString[-28:-21], '0' + bitString[-21:-14], '0' + bitString[-14:-7], '0' + bitString[-7:]]
        framesSize = self._hexPad(hex(int(fs_7bit[0], 2))[2:], 2) + self._hexPad(hex(int(fs_7bit[1], 2))[2:], 2) + self._hexPad(hex(int(fs_7bit[2], 2))[2:], 2) + self._hexPad(hex(int(fs_7bit[3], 2))[2:], 2)
        header = self._hexStringToChars('494433030000' + framesSize)
        return header + allFrames


    def _updateTagSize(self):
        """ As it says """
        self.cleanedTagSize = 10
        for frame in self.frames.itervalues():
            self.cleanedTagSize += (11 + len(frame))


    def _insertFrame(self, frameType, data):
        """ Create a new frame and add to the list of frames for current file """
        # NB: Can insert even if no header exists. TAGv2-header is automatically created when writing file
        self.frames[frameType] = data
        return 1


    def _getSecondaryTagData(self):
        """ Fletter Data fra Ape og V1, og indsaette det i V23 """
        # Flet data
        data = self.v1Data
        for x in self.apeData:
            if x[0].capitalize() == 'Title':
                if len(x[3]) > len(data[0]):
                    data[0] = x[3]
            if x[0].capitalize() == 'Artist':
                if len(x[3]) > len(data[1]):
                    data[1] = x[3]
            if x[0].capitalize() == 'Album':
                if len(x[3]) > len(data[2]):
                    data[2] = x[3]
            if x[0].capitalize() == 'Year':
                if len(x[3]) > len(data[3]):
                    data[3] = x[3]
            if x[0].capitalize() == 'Track':
                if len(x[3]) > len(data[4]):
                    data[4] = x[3]
        # Create frames
        if len(data[0]) != 0:
            self._insertFrame('TIT2', data[0])
        if len(data[1]) != 0:
            self._insertFrame('TPE1', data[1])
        if len(data[2]) != 0:
            self._insertFrame('TALB', data[2])
        if len(data[3]) != 0:
            self._insertFrame('TYER', data[3])
        if len(data[4]) != 0 and data[4] != '0':
            self._insertFrame('TRCK', data[4])
        self.flags = '00000000'
        self._updateTagSize()
        self.version = 3
        self.v1Data = []
        self.apeData = []
        return 1


    def _cleanV2(self):
        """ Updates data from v2X to match V23 format and removes unwanted frames """
        self.version = 3
        # Values not in the transTable will be omitted, and thus lost
        newDict = {}
        for key in self.frames.iterkeys():
            if key == 'TRCK':   # Check to remove xx/yy - format
                if '/' in self.frames[key]:
                    self.frames[key] = self.frames[key].split('/')[0]
            if key in transTable:
                newDict[transTable[key]] = self.frames[key]
            elif key in accepted:
                newDict[key] = self.frames[key]
        self.frames = newDict
        self._updateTagSize()
        self.v1Data = []
        self.apeData = []
        return 1


    def _readTagV1(self):
        """ Reads TagV1 if it exists, and saves it in the list 'self.v1Data'. Cuts TAG from file-data! """
        if self.fileCont[-128:-125] == 'TAG':
            v1Tag_raw = self.fileCont[-125:]
            self.fileCont = self.fileCont[:-128]
            self.v1Data = [v1Tag_raw[00:30]]
            self.v1Data.append(v1Tag_raw[30:60])
            self.v1Data.append(v1Tag_raw[60:90])
            self.v1Data.append(v1Tag_raw[90:94])
            self.v1Data.append(str(ord(v1Tag_raw[123:124])))
            if self.v1Data[4] == 0: self.v1Data[4] = ''
            for nr, item in enumerate(self.v1Data):
                self.v1Data[nr] = item.replace('\x00', '')
            return 1
        else:
            return 0


    def _readTagV2(self):
        """ Reads TagV2 if it exists, and saves all to self. Cuts TAG from file-data! """
        if self.fileCont[0:3] != 'ID3':
            return 0                     # Non-ID3 file, aborting
        pointer = 3
        self.version  = ord(self.fileCont[pointer])
        self.orgVersion = self.version
        pointer += 1
        self.revision = ord(self.fileCont[pointer])
        pointer += 1
        self.flags = bin(ord(self.fileCont[pointer]))[2:].rjust(8, '0')
        pointer += 1
        self.tagSize = (ord(self.fileCont[pointer]) << 21) + (ord(self.fileCont[pointer + 1]) << 14) + (ord(self.fileCont[pointer + 2]) << 7) + ord(self.fileCont[pointer + 3])
        pointer = 10
        # Start reading frames
        if self.version > 2:
            headerSize = 4
        else:
            headerSize = 3
        while pointer < self.tagSize:
            header =  self.fileCont[pointer:pointer + headerSize]
            pointer = pointer + headerSize
            if self.version == 4:
                sizeBytes = self.fileCont[pointer:pointer + headerSize]
                size = (ord(sizeBytes[0]) << 21) + (ord(sizeBytes[1]) << 14) + (ord(sizeBytes[2]) << 7) + ord(sizeBytes[3])
            else:
                size = int(self.fileCont[pointer:pointer + headerSize].encode('hex'), 16)
            if size == 0: break
            pointer = pointer + headerSize
            if self.version != 2:
                flagByte1 = self._hexPad(str(ord(self.fileCont[pointer:pointer + 1])), 2)
                flagByte2 = self._hexPad(str(ord(self.fileCont[pointer + 1:pointer + 2])), 2)
                pointer = pointer + 2
                flags = flagByte1 + flagByte2
            if header == 'APIC' and self.version == 4:
                pointer = pointer + 4 # Skipping the 4 ekstra size-bytes of V2.4 APIC, as we will calculate them anew
                size -= 4
            frame = self.fileCont[pointer:pointer + size]
            pointer = pointer + size
            encoding = frame[0]
            if self.version == 2: # Cleaning up frame
                frame = frame[1:-1]
            else:
                frame = frame[1:]
            if (len(frame) > 0): # Do not add empty frames
                self.frames[header] = frame.strip()
        # Removing Tag
        self.fileCont = self.fileCont[self.tagSize + 10:]
        # Removing padding, if any
        pointer = 0
        while pointer < len(self.fileCont):  # i.e. file is not 0
            if self.fileCont[pointer].encode('hex') != '00':
                if self.fileCont[pointer:pointer + 2].encode('hex') != 'fffb':
                    break
                else:
                    pointer += 10
            pointer += 1
        if pointer < 5: # Hvis pointer < 5, er helvede loes!
            pointer = 5
        self.fileCont = self.fileCont[pointer - 5:]
        if self.frames.has_key('TRCK') and self.frames['TRCK'] == '0':
            self.frames.pop('TRCK')
        return 1


    def _readApe(self):
        """  Reads APE Tag if it exists, and saves it in the list 'self.apeData'.  Cuts TAG from file-data! """
        if self.fileCont.find("APETAGEX") != -1:
            apeStart = self.fileCont.find("APETAGEX") + 8
        else:
            return 0
        apeVersion = int(self._reverseHex(self.fileCont[apeStart:apeStart + 4]).encode('hex'), 16)
        apeSize = int(self._reverseHex(self.fileCont[apeStart + 4:apeStart + 8]).encode('hex'), 16)
        apeItems = int(self._reverseHex(self.fileCont[apeStart + 8:apeStart + 12]).encode('hex'), 16)
        apeFlags = self._reverseHex(self.fileCont[apeStart + 12:apeStart + 16])  # Not used, don't know how to or why?
        # Start reading frames
        # Frame Format : LENGTH (4) - Flags?(4) - Identifier(?) - IdStop (1, blank) - Data (Length)
        pointer = apeStart + 24
        while self.fileCont[pointer] < len(self.fileCont) and len(self.apeData) < apeItems:
            frLength = int(self._reverseHex(self.fileCont[pointer:pointer + 4]).encode('hex'), 16)
            frFlags = int(self._reverseHex(self.fileCont[pointer + 4:pointer + 8]).encode('hex'), 16)
            pointer += 8
            fr_Identifier = ''
            while self.fileCont[pointer].encode('hex') != '00':
                fr_Identifier += self.fileCont[pointer]
                pointer += 1
            pointer += 1
            fr_data = self.fileCont[pointer:pointer + frLength]
            pointer += frLength
            self.apeData.append([fr_Identifier, frLength, frFlags, fr_data])
        # Check if footer exists
        if self.fileCont[pointer:pointer + 8] == 'APETAGEX':
            apeEnd = pointer + 32
        else:
            apeEnd = pointer
        # Destroy APETag
        self.fileCont = self.fileCont.replace(self.fileCont[apeStart:apeEnd], '')
        if self.fileCont.find("APETAGEX") != -1: # Destroy other tag, if any
            self.fileCont = self.fileCont.replace(self.fileCont[self.fileCont.find('APETAGEX'):self.fileCont.find('APETAGEX') + 8], '')
        return 1


    def showVersion(self):
        """ Shows version of TAG-data contained in self. Designed for mass-processing of files """
        if self.contV2:
            version = 'V2.' + str(self.version) + '.' + str(self.revision)
        else:
            version = '----'
        print '[' + str(self.contV1) + ' ' + str(self.contApe) + ']', version, "         ('" + self.fileName + "')"


    def showData(self):
        """ Shows all TAG-data contained in self """
        print '|'
        print '|'
        print "|Filename : '" + self.fileName + "'"
        print '*--- ID3V2 Tag Data ------------------------------------------'
        if self.contV2:
            print '|   Tag version : 2.' + str(self.version) + '.' + str(self.revision)
            print '|   Flags       :', self.flags
            if self.cleanedTagSize != 0:
                print '|   Size of Tag :', self.cleanedTagSize
            else:
                print '|   Size of Tag :', self.tagSize
            print '|   ', len(self.frames), 'frames found in this tag :'
            for key in self.frames.iterkeys:
                string1 = '|       ' + key + ' (' + str(len(self.frames[key])) + ' bytes)'
                if len(str(self.frames[key])) < 200: string2 = "'" + str(self.frames[key]) + "'"
                else: string2 = '<hidden>'
                print string1 + ((25 - len(string1)) * ' ') + " : " + string2
        else:
            print '|   <No ID3V2 Tag data found in file>'
        print '*--- ID3V1 Tag Data ------------------------------------------'
        if self.contV1:
            print "|   Track Name : '" + self.v1Data[0] + "'"
            print "|   Band Name  : '" + self.v1Data[1] + "'"
            print "|   Album      : '" + self.v1Data[2] + "'"
            print "|   Year       : '" + self.v1Data[3] + "'"
            print "|   Track No   : '" + self.v1Data[4] + "'"
        else:
            print '|   <No ID3V1 Tag data found in file>'
        print '*--- APE Tag Data --------------------------------------------'
        if self.contApe:
            for ape in self.apeData:
                print ape[0].capitalize() + ((25 - len(ape[0])) * ' ') + " : " + ape[3]
        else:
            print '|   <No APE Tag data found in file>'
        print '*-------------------------------------------------------------'
        print


    def fixData(self):
        """ Identifies data version, updates TAG data """
        if self.status.tagStatus[2]:
            self._cleanV2()
        elif self.status.tagStatus[0] or self.status.tagStatus[1]:
            self._getSecondaryTagData()
        else:
            return 0 # skip file, as it has no tag
        self.status.update()
        return 1


    def writeFile(self, outFile=None):
        """  Writes file """
        if outFile == None: outFile = self.path
        fp = open(outFile, 'wb')
        fp.write(self._createHeader())
        fp.write(self.fileCont)
        fp.close()
        return 1


    def _getNewYear(self, name):
        """ Generates new year-string, for years not using 4-digit format """
        cleanName = ''
        if name == '[unknown]' or len(name) == 0:
            return ''
        for char in name:
            if char.isdigit():
                cleanName += char
        cleanName = cleanName[-2:]
        if int(cleanName) > time.localtime().tm_year - 2000:
            cleanName = '19' + str(cleanName)
        else:
            cleanName = '20' + str(cleanName)
        return cleanName


    def getNameData(self):
        """ Returns the data needed to rename a file/directory. Should be preceeded by fixData """
        data = {}
        if self.frames.has_key('TPE1'): data['artist'] = self.frames['TPE1']
        if self.frames.has_key('TIT2'): data['titel'] =  self.frames['TIT2']
        if self.frames.has_key('TYER'):
            data['year'] =   self.frames['TYER']
            if len(data['year']) != 4: data['year'] = self._getNewYear(data['year'])
        if self.frames.has_key('TRCK'):
            data['track'] = self.frames['TRCK'].split('/')[0]   # to avoid '1/13'-format
            if data['track'] != '' and len(data['track']) < 2: data['track'] = '0' + data['track']
        if self.frames.has_key('TALB'): data['album'] =  self.frames['TALB']
        return data


    def addPicture(self, picPath):
        """ Adds a picture to the file in memory"""
        fileName, fileExt = os.path.splitext(picPath)
        if fileExt.upper() != '.JPG' and fileExt.upper() != '.JPEG' and fileExt.upper() != '.PNG':
            return 0
        # Chek whether file already has picture
        if self.frames.has_key('APIC'):
            return 0
        fp = open(picPath, 'rb')
        picData = fp.read()
        fp.close()
        picHex = ''
        self._insertFrame('APIC', picData)
        return 1


class ProcessDirs():
    """ Klasse som tager et dir, og processerer undebiblioteker og filer """

    totalDirs = 0
    totalFiles = 0
    image = 0
    try: from PIL import Image
    except: pass

    def __init__(self, selfDir):
        self.path = selfDir
        self.subDirs = []
        self.filesMP3 = []
        self.filesPic = []
        self.filesOthers = []
        self.picture = 0
        self.hasPic = False
        self.empty = False
        self.renameDirs = False
        self.statics = [None, None, None]
        if args.extract: self._extractFromName()
        else: self._processDir()


    def _processDir(self):
        """ Processes all filers in the directory, and calls itself each time a new is found """
        ProcessDirs.totalDirs += 1
        # Sorting directory
        for item in listdir(self.path):
            if os.path.isdir(os.path.join(self.path,item)):
                self.subDirs.append(item)
            elif item.upper()[-4:] == '.MP3':
                self.filesMP3.append(item)
            elif item.upper()[-4:] in ['.PNG', '.JPG', 'JPEG']:
                self.filesPic.append(item)
            else:
                self.filesOthers.append(item)
        if len(self.filesPic) + len(self.filesOthers) + len(self.filesMP3) == 0:
            self.empty = True
        self._handlePictures()
        # Print status
        if len(self.path[len(baseDir):]) <= 0:
            print '[' + self.path + ']' + ' ' * (68 - len(self.path)),
        else:
            print '[' + self.path[len(baseDir):] + ']' + ' ' * (74 - len(self.path)),
        if self.hasPic:
            print ' [Contains Picture]'
        else:
            print ' [No Picture]'
        print '*----------------------------------------------------------------------------------------'
        # Handle unknown formats
        if len(self.filesOthers) > 0:
            print '|   Cleaning up Pictures:'
            print '*----------------------------'
        for x in range(len(self.filesOthers), 0, -1):
            try:
                os.remove(os.path.join(self.path,self.filesOthers[x - 1]))
                print '|      (removed ' + self.filesOthers[x - 1] + ')'
                self.filesOthers.remove(self.filesOthers[x - 1])
            except Exception:
                print '|      (failed to remove ' + self.filesOthers[x - 1] + ')'
            print '*----------------------------'
        Col_renameData = self._handleMP3s()
        # Fix directoryname
        if len(Col_renameData) > 1 and args.renamedirs:
            renameDirData = self._compareFields(Col_renameData)
            newDirName = self._getNewDirName(renameDirData,  args.renamefiles)
            oldDir = os.path.split(self.path)[-1]
            if args.renamedirs and newDirName != oldDir and not '[unknown]' in newDirName:
                if self._renameDir(newDirName):
                    self.path = os.path.join(os.path.split(self.path)[0], newDirName)
                    print '*----------------------------'
                    print "|   Renamed directory to '" + newDirName + "'"
                    print '*----------------------------'
        # Remove all picture, if any
        if len(self.filesPic) > 0:
            print '|   Cleaning up Pictures:'
            for x in range(len(self.filesPic), 0, -1):
                try:
                    os.remove(os.path.join(self.path,self.filesPic[x - 1]))
                    print '|      (removing ' + self.filesPic[x - 1] + ')'
                except:
                    print '|      (failed to remove ' + self.filesPic[x - 1] + ')'
                self.filesPic.remove(self.filesPic[x - 1])
        # Handle empty dir
        if self.empty:
            print '|   <empty directory>'
        print '*----------------------------------------------------------------------------------------'
        print
        print
        # Handle Directories
        if len(self.subDirs) > 0 and args.recurse:
            for d in self.subDirs:
                ProcessDirs(os.path.join(self.path,d))


    def _handlePictures(self):
        """ Handles Pictures in the directory; inserts pictures that matches filenames, then chooses central picture, deletes the rest """
        # Check if picture-filenames matches any mp3-filename
        for pic in reversed(self.filesPic):
            if pic[:-3] + 'mp3' in self.filesMP3:
                print "  File/Pic match found. Adding '" + pic[:-4] + "' to file...."
                fp = MP3Tag(os.path.join(self.path, pic[:-3] + 'mp3'))
                fp.fixData()
                fp.addPicture(os.path.join(self.path, pic))
                fp.writeFile()
                fp = None
                self.filesPic.remove(pic)
                os.remove(os.path.join(self.path, pic))
        if len(self.filesPic) > 1:
            print ' ' + str(len(self.filesPic)) + " pictures found in '" + self.path + "'"
            print '   Please chose which to use : '
            valid = []
            suggested = 0
            sugText = ''
            for nr, pic in enumerate(self.filesPic):
                valid.append(str(nr + 1))
                if self.Image:
                    with open(str(os.path.join(self.path,pic)), 'rb') as ph:
                        openPic = self.Image.open(ph)
                    openPic = self.Image.open(os.path.join(self.path,pic))
                    print '      ', str(nr + 1) + " '" + pic + "' (" + str(openPic.size[0]) + 'x' + str(openPic.size[1]) + ')'
                else:
                    print '      ', str(nr + 1) + " '" + pic + "' (" + str(os.path.getsize(os.path.join(self.path,pic)) / 1000) + ' KB)'
                if 'FRONT' in pic.upper() or 'COVER' in pic.upper():
                    suggested = nr + 1
                    valid.append('')
                    sugText = " (or space to accept suggested : '" + pic + "')"
            openPic = self.Image.new('1', (10,10))   # This is to force PIL to let go of last picture processed
            select = 0
            while select not in valid:
                select = raw_input('   Choose a valid number' + sugText + ' : ')
            if select == '': select = suggested
            print
            print
            self.picture = self.filesPic[int(select) - 1]
        elif len(self.filesPic) == 1:
            self.picture = self.filesPic[0]
        if self.picture != 0:
            self.hasPic = True
            if self.Image:
                # Resize to =< 500
                with open(str(os.path.join(self.path,self.picture)), 'rb') as ph:
                    openPic = self.Image.open(ph)
                    if openPic.size[0] > 500:
                        openPic.thumbnail((500,500),self.Image.ANTIALIAS)
                        openPic.save(os.path.join(self.path,self.picture))
        return 1


    def _handleMissingData(self, obj, prevValues):
        """ Forsoeger at finde tracknr i filnavn & og beder om brugerinput paa artist/title/album hvis de mangler """
        track = obj._getTrackFromName(obj.fileName)
        if track != False:
             obj._insertFrame('TRCK', track)
        artist = ''
        title = ''
        album = ''
        sugArtist = None
        sugTitle = None
        sugAlbum = None
        suggText = ['', '', '']
        # Suggest from previous file
        if prevValues[0] != None and prevValues[0] != '':
            sugArtist = prevValues[0]
            suggText[0] = " ('" + sugArtist + "') "
        if prevValues[1] != None and prevValues[1] != '':
            sugAlbum = prevValues[1]
            suggText[2] = " ('" + sugAlbum + "') "
        # Suggest from filename
        if '-' in obj.fileName:
            split = obj.fileName.split('-')
            if sugArtist == None and len(split[0].strip()) > 2:
                sugArtist = split[0].strip()
                suggText[0] = " ('" + sugArtist + "') "
            if sugTitle == None and len(split[1].strip()) > 2:
                sugTitle = split[1].strip()
                suggText[1] = " ('" + sugTitle + "') "
        if obj.frames.has_key('TPE1'):
            artist = obj.frames['TPE1']
        if obj.frames.has_key('TIT2'):
            title = obj.frames['TIT2']
        if obj.frames.has_key('TALB'):
            album = obj.frames['TALB']
        if args.suppresswarn:    # NB! Does NOT suppress dialogue if no data can be suggested
            if sugArtist != None: artist = sugArtist
            if sugTitle  != None: title = sugTitle
            if sugAlbum  != None: album = sugAlbum
        while artist == '':
            artist = raw_input('\n|         Please input missing ARTIST Tag' + suggText[0] + ': ')
            if artist == '' and sugArtist != None: artist = sugArtist
        obj._insertFrame('TPE1', artist)
        while title == '':
            title = raw_input('\n|         Please input missing TITLE Tag' + suggText[1] + ': ')
            if title == '' and sugTitle != None: title = sugTitle
        obj._insertFrame('TIT2', title)
        while album == '':
            album = raw_input('\n|         Please input missing ALBUM Tag' + suggText[2] + ': ')
            if album == '' and sugAlbum != None: album = sugAlbum
        obj._insertFrame('TALB', album)
        return 1


    def _updateLast(self, frames):
        """ Returns TagData from frames"""
        ud = [None, None]
        if frames.has_key('TPE1'):
            ud[0] = frames['TPE1']
        if frames.has_key('TALB'):
            ud[1] = frames['TALB']
        return ud


    def _handleMP3s(self):
        """ Reads and checks the Tag, if any. Rewrites the filename if applicable """
        canWarn = 1
        prevFileData = [None, None, None]
        Col_renameData = []
        for fil in self.filesMP3:
            ProcessDirs.totalFiles += 1
            cp = MP3Tag(os.path.join(self.path, fil))
            cp.status.update()
            status = cp.status.getFullStatus()
            if not cp.status.pictureStatus and not self.hasPic and canWarn and not args.suppresswarn:
                print '|'
                raw_input('| NB! Directory contains no picture, and mp3-files without internal pictures. <return> to continue...')
                print '|'
                canWarn = 0
            print "| " + cp.status.getFullStatus() + " '" + fil + "'",
            if not cp.status.pictureStatus and self.hasPic == True:
                cp.addPicture(os.path.join(self.path, self.picture))
            if cp.status.getTagStatus != '00110' or not cp.status.pictureStatus or args.rewritetags:
                cp.fixData()
                if not cp.status.hasVitalFrames():
                    self._handleMissingData(cp, prevFileData)
                # FixString Text-frames
                for key in cp.frames.iterkeys():
                    if key.startswith('T'):
                        cp.frames[key] = self._fixString(cp.frames[key])    # Notice any inserts are NOT fixed, to allow more user control
                if cp.frames.has_key('TPE1') and args.artist != None:
                   cp.frames['TPE1'] = args.artist
                if cp.frames.has_key('TYER') and args.year != None:
                   cp.frames['TYER'] = args.year
                if cp.frames.has_key('TALB') and args.album != None:
                   cp.frames['TALB'] = args.album
                if args.updatetags or args.forcerewrite:
                    cp.writeFile(os.path.join(self.path, fil))
            prevFileData = self._updateLast(cp.frames)
            # Fix filename
            renameFileData = cp.getNameData()
            Col_renameData.append(renameFileData)
            cp.status.update()
            status = cp.status.getFullStatus()
            cp = None
            newFileName = self._getNewFileName(renameFileData, args.renamefiles)
            renameLen = 0
            if args.renamefiles and newFileName != fil and not '[unknown]' in newFileName:
                self._renameFile(fil, newFileName)
                print " ===>  '" + newFileName + "' ",
                renameLen = len(newFileName) + 11
            print ' ' * (50 - len(fil) - renameLen),
            print status
        return Col_renameData


    def _compareFields(self, data):
        """ Compares sets of data to determine wheter they are identical """
        eightyPercent = len(data) * 8.0 / 10
        fields = {'album': '[unknown]', 'artist': 'Various Artists', 'year': '[unknown]'}
        stats = [{}, {}, {}]
        for entry in data:
            if entry.has_key('album'):
                if not entry['album'] in stats[0]:
                    stats[0][entry['album']] = 1
                else:
                    stats[0][entry['album']] += 1
            if entry.has_key('artist'):
                if not entry['artist'] in stats[1]:
                    stats[1][entry['artist']] = 1
                else:
                    stats[1][entry['artist']] += 1
            if entry.has_key('year'):
                if not entry['year'] in stats[2]:
                    stats[2][entry['year']] = 1
                else:
                    stats[2][entry['year']] += 1
        # Choose value if any matches 80% of entries
        for key in stats[0]:
            if stats[0][key] >= eightyPercent:
                fields['album'] = key
        for key in stats[1]:
            if stats[1][key] >= eightyPercent:
                fields['artist'] = key
        for key in stats[2]:
            if stats[2][key] >= eightyPercent:
                fields['year'] = key
        return fields


    def _getNewFileName(self, data, form):
        """ Generates new directoryname"""
        if form == 1:
            return data['artist'] + ' - ' + data['titel'] + '.mp3'
        elif form == 2:
            if data.has_key('track'):  # We cannot be sure to have a track. If not, use alternative renaming pattern
                return data['track'] + ' - ' + data['titel'] + '.mp3'
            else:
                return data['artist'] + ' - ' + data['titel'] + '.mp3'
        else:
            sys.exit('Unknown form given. Must get values 1 or 2')


    def _getNewDirName(self, data, form):
        """ Generates new filename"""
        if form == 1:
            return data['artist'] + ' - ' + data['album']
        elif form == 2:
            return data['year'] + ' - ' + data['album']
        else:
            sys.exit('Unknown form given. Must get values 1 or 2')


    def _renameFile(self, oldName, newName):
        """ Tries to rename file using ID3 Tag-data, and if fails, tries to rename to name + count """
        oldPath = os.path.join(self.path, oldName)
        newPath = os.path.join(self.path, newName)
        try:
            os.rename(oldPath, newPath)
        except:
            count = 2
            while os.path.exists(oldPath + str(count)):
                count += 1
            try:
                os.rename(oldPath, newPath[:-4] + str(count) + '.mp3')
            except:
                return 0    # Leave old name
        return 1


    def _renameDir(self, newName):
        """ Tries to rename file using ID3 Tag-data """
        newPath = os.path.join(os.path.split(self.path)[0], newName)
        try:
            os.rename(self.path, newPath)
        except:
            return 0    # Leave old name
        return 1


    def _fixString(self, strInd):
        """ Converts string to a common format """
        strInd = str(strInd).lower()
        if '(' in strInd and not ')' in strInd:
            strInd = strInd.split('(')[0]
        strOut = ''
        banned = [0, 255, 254]  # Forbandede BOM fjernes her, plus deres tomme tegn
        # Process each letter
        for char in strInd:
            if ord(char) not in banned:
                if len(strOut) == 0:
                    char = char.upper()
                else:
                    if strOut[-1] == '.' or strOut[-1] == ' ' or strOut[-1] == '(':
                        char = char.upper()
                if char == '%' or char == '_':
                    char = ' '
                elif char == '[':
                    char = '('
                elif char == ']':
                    char = ')'
                elif char == '':
                    char = chr(0)   # Will be ignored
                if char not in renameIllegal:
                    strOut = strOut + char
        # Process each word
        fixSplit = strOut.split()
        for nr, word in enumerate(fixSplit):
            if nr != 0: # First word can never be un-capitalized
                for item in smallWords:
                    if word.upper() == item.upper():
                        fixSplit[nr] = item
            for item in romanNumbers:
                if word.upper() == item.upper():
                    fixSplit[nr] = item
            for item in casedWords:
                if word.upper() == item.upper():
                    fixSplit[nr] = item
        return ' '.join(fixSplit)


    def _extractFromName(self):
        """ Parses the name of files and inserts information into Tags. """
        firstRun = True
        ProcessDirs.totalDirs += 1
        for fil in listdir(self.path):
            if fil.upper()[-4:] == '.MP3':
                ProcessDirs.totalFiles += 1
                if firstRun:  # If this is the first file in the directory, set up
                    print 'Setting up Extraction :'
                    print '*' + '-' * 60
                print '| Filename : "' + fil + '"'
                if firstRun:
                    print '*' + '-' * 60
                    split1 = int(raw_input('| Split filename after which word? : ')) 
                    split2 = raw_input('| Split filename again after which word? (<return> to split only once) : ')
                    if split1 == '': split1 = 0 
                    else: split1 = int(split1)
                    if split2 == '': split2 = 0 
                    else: split2 = int(split2)
                extractedData = {'TPE1': '<none>', 'TIT2': '<none>', 'TYER': '<none>', 'TRCK': '<none>', 'TALB': '<none>' }
                split = fil[:-4].replace('-', '').split()
                if split2:
                    result = [' '.join(split[:split1]), ' '.join(split[split1:split2]), ' '.join(split[split2:])]
                else:
                    result = [' '.join(split[:split1]), ' '.join(split[split1:])]
                if firstRun:
                    print '| Extracted these parts : ', result
                    print '| Extraction resulted in', len(result), 'parts. Please assign these parts (<space> to skip) : '
                    artistNr = raw_input('|    Band Name = (1-' + str(len(result)) + ') : ')
                    if artistNr == '' : artistNr = 0
                    else: artistNr = int(artistNr)
                    titelNr = raw_input('|    Titel =     (1-' + str(len(result)) + ') : ')
                    if titelNr == '' : titelNr = 0
                    else: titelNr = int(titelNr)
                    yearNr = raw_input ('|    Year =      (1-' + str(len(result)) + ') : ')
                    if yearNr == '' : yearNr = 0
                    else: yearNr = int(yearNr)
                    trackNr = raw_input('|    Track No =  (1-' + str(len(result)) + ') : ')
                    if trackNr == '' : trackNr = 0
                    else: trackNr = int(trackNr)
                    albumNr = raw_input('|    Album =     (1-' + str(len(result)) + ') : ')
                    if albumNr == '' : albumNr = 0
                    else: albumNr = int(albumNr)
                if artistNr: extractedData['TPE1'] = result[artistNr - 1]
                if titelNr:  extractedData['TIT2'] = result[titelNr - 1]
                if yearNr:   extractedData['TYER'] = result[trackNr - 1]
                if trackNr:  extractedData['TRCK'] = result[trackNr - 1]
                if albumNr:  extractedData['TALB'] = result[trackNr - 1]
                if firstRun:
                    print '| This is the result of the extraction :'
                    print '* ----------------------------------------'
                    print '| Artist   : ' + extractedData['TPE1']
                    print '| Titel    : ' + extractedData['TIT2']
                    print '| Year     : ' + extractedData['TYER']
                    print '| Track No : ' + extractedData['TRCK']
                    print '| Album    : ' + extractedData['TALB']
                    print '* ----------------------------------------'
                if not firstRun or raw_input('| Please type "YES" to continue extracting on all other files, anything else to quit : ').upper() == 'YES':
                    cp = MP3Tag(os.path.join(self.path, fil))
                    for key, value in extractedData.iteritems():
                        if value != '<none>':
                            cp._insertFrame(key, value)
                    cp.writeFile(os.path.join(self.path, fil))
                    cp = None
                else:
                    print
                    sys.exit('Extraction cancelled by user....')
                firstRun = False




# -- Main -------------------------------------------------------

parser = argparse.ArgumentParser(formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=40))
parser.add_argument("-e", "--extract",      action="store_true", default=False, help="Extracts info from the filename")
parser.add_argument("-r", "--recurse",      action="store_true", default=False, help="Recurses any subdirectory encountered")
parser.add_argument("-w", "--rewritetags",  action="store_true", default=False, help="Forces rewriting of the tag, even if no changes are made")
parser.add_argument("-t", "--updatetags",   action="store_true", default=True,  help="Processes tags in files and rewrites the files if changes are made")
parser.add_argument("-s", "--suppresswarn", action="store_true", default=False, help="Suppress warnings about missing pictures and confirmation of suggested TAG Data")
parser.add_argument("-f", "--renamefiles",  type=int, choices=[0, 1, 2], default=0, help="Changes the name of files, using pattern 1 = [Artist - Titel] or 2 = [Track - Titel]")
parser.add_argument("-d", "--renamedirs",   type=int, choices=[0, 1, 2], default=0, help="Changes the name of dirs,  using pattern 1 = [Artist - Album] or 2 = [Year - Album]")
parser.add_argument("--artist", action='store', dest='artist', help="Sets artist value for all files")
parser.add_argument("--year",   action='store', dest='year', help="Sets year value for all files")
parser.add_argument("--album",  action='store', dest='album', help="Sets album value for all files")
args = parser.parse_args()

if args.extract == True:
    if args.rewritetags == True or args.renamefiles == 1 or args.renamedirs == 1:
        print 'usage: TagEd [-e] | [-h] [-w] [-t] [-s] [-f {1,2}] [-d {1,2}]\nPROG: error: argument "-e" / "--extract" cannot be used with any other argument'
        sys.exit()
    else:
        print 'Please notice that extract-mode does not recurse directories'

baseDir = os.getcwd()
# baseDir = 'C:\\Users\\PrinceVlad\\Desktop\\test'
origstdout = sys.stdout
sys.stdout = PrintLog()

print
print "Start processing, directory is '" + baseDir + "' :"
print
pointer = ProcessDirs(baseDir)
print '--------------------------------------------------'
print 'Files processed       : ' + str(pointer.totalFiles)
print 'Directories processed : ' + str(pointer.totalDirs)
print '--------------------------------------------------'
print 'Job completed at', time.strftime("%Y-%m-%d-%H-%M-%S", time.gmtime())
print

PrintLog.close(sys.stdout)
sys.stdout = origstdout


# Run = TagEd4.py -rws -f 2 -d 2

# -- Problems ---------------------------------------------------

# - Kan ikke laese stier med specielle characters





