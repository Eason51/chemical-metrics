
from html.parser import HTMLParser
from chemdataextractor import Document
import easyocr
from torch._C import ConcreteModuleTypeBuilder

TARGET = "janus kinase"
fileId = 6
DOMAIN = "https://pubs.acs.org"

# hold title content after parsing html file
titleText = ""
# hold links to abstract images after parsing html file
imgArr = []
# hold abstract content after parsing html file
abstractText = ""

# hold all identified molecule names
moleculeArr = []
# hold all identified compound names
compoundArr = []
# hold all identified ic50 values
ic50Arr = []

# hold the molecule name
molecule = ""
# hold the compound name
compound = ""
# hold the ic50 value
ic50Value = ""

# identify whether a string is "ic50"
def ic50(string):
    string = string.lower()
    pos = string.find("ic")
    if(pos == -1):
        return False
    
    pos += 2
    if(pos >= len(string)):
        return False
    if not(string[pos] == "5" or string[pos] == "s" or string[pos] == "S"):
        return False
    pos += 1
    if(pos >= len(string)):
        return False
    if not (string[pos] == "0" or string[pos] == "O" or string[pos] == "o"):
        return False
    return True

# identify whether a string is in the form of a compound name
def compoundName(string):
    if(string == ""):
        return False
    string = string.lower().strip()
    if(string.isdigit()):
        return True
    if(len(string) >= 2 and string[:-1].isdigit() and string[-1].isalpha()):
        return True

# open a file locally, should be retrieved through http request in real programs
with open(f"files/{TARGET}/file{fileId}.html", encoding="utf-8") as inputFile:

    # parsing a html file
    class TableParser(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)

            self.imgArr = []
            self.abstractText = ""

            self.abstractFound = False
            self.figureFound = False
            self.imgLinkFound = False
            self.textFound = False

            self.titleFound = False
            self.titleText = False



        def handle_starttag(self, tag, attrs):
            if(tag == "div" and len(attrs) >= 1):
                for attr in attrs:
                    if (attr[0] == "class" and attr[1] == "article_abstract-content hlFld-Abstract"):
                        self.abstractFound = True
                        break
            if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content"):
                self.abstractText += " . "
                self.abstractFound = False
            if(self.abstractFound and tag == "figure"):
                self.figureFound = True
            if(self.figureFound and tag == "a" and len(attrs) >= 2):
                title = link = ""
                for attr in attrs:
                    if(attr[0] == "title"):
                        title = attr[1]
                    elif(attr[0] == "href"):
                        link = DOMAIN + attr[1]
                if(title == "High Resolution Image"):
                    self.imgArr.append(link)
            if(self.abstractFound and tag == "p" and len(attrs) == 1 and attrs[0][1] == "articleBody_abstractText"):
                self.textFound = True
            if(tag == "h1" and len(attrs) == 1 and attrs[0][1] == "article_header-title"):
                self.titleFound =True
            if(self.titleFound and tag == "span"):
                self.titleText = True


        def handle_data(self, data):
            if(self.textFound):
                self.abstractText += data
            if(self.titleText):
                global titleText
                titleText = data

        
        def handle_endtag(self, tag):
            if(self.figureFound and tag == "figure"):
                self.figureFound = False
            if(self.textFound and tag == "p"):
                self.textFound = False
            if(self.titleFound and tag == "h1"):
                self.titleFound = False
            if(self.titleText and tag == "span"):
                self.titleText = False

    # parse the given html file with TableParser()
    tableParser = TableParser()
    tableParser.feed(inputFile.read())

    imgArr = tableParser.imgArr
    abstractText = tableParser.abstractText

# find all identified molecule names inside of title
doc = Document(titleText)
for NR in doc:
    moleculeArr.append(NR.cems[0])

# identify all text within the abstract image
reader = easyocr.Reader(["en"], gpu = False)
# retrieve picture through http request
positionResult = reader.readtext("img.jpg")
contentResult = reader.readtext("img.jpg", detail = 0)

# identify the ic50 value from abstract image

# find ic50 keyword location
elements = []
for element in positionResult:
    if(ic50(element[1].lower())):
        elements.append(element)

# find the rightmost ic50 keyword
position = []
centerX = 0
for element in elements:
    localCenterX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
    if(localCenterX > centerX):
        centerX = localCenterX
        position = element

# check if ic50 keyword contains the required value
valueFound = False
for word in position[1].lower().split():
    if("nm" in word):
        valueFound = True
        break

# if ic50 keyword contains the value, retrieve the value
if(valueFound):
    pos = position[1].find("=")
    if(pos == -1 or (pos + 1) >= len(position[1])):
        valueFound = False
    else:
        ic50Value = position[1][pos + 1: ]

# if no value is found in ic50 keyword
else:
    # find all keywords conataining "nm"
    nmArr = []
    for element in positionResult:
        if("nm" in element[1].lower() and min(element[0][0][0], element[0][3][0]) >= max(position[0][1][0], position[0][2][0])):
            nmArr.append(list(element))
            nmArr[0][1] = nmArr[0][1].lower()
    
    for element in nmArr:
        # if the keyword contains only "nm", needs to contain it with the number before it e.g.: keyword(50), keyword(nm), combined into keyword(50nm)
        if(element[1].strip() == "nm"):

            downY = max(element[0][2][1], element[0][3][1])
            topY = min(element[0][0][1], element[0][1][1])
            leftX = (element[0][0][0] + element[0][3][0]) / 2
            rightX = (element[0][1][0] + element[0][2][0]) / 2
            valueElement = []
            xDistance = element[0][1][0]
            for localElement in positionResult:
                localCenterY = (localElement[0][0][1] + localElement[0][1][1] + localElement[0][2][1] + localElement[0][3][1]) / 4
                # same y level as "nm" keyword
                if(localCenterY <= downY and localCenterY >= topY):
                    localRightX = (localElement[0][1][0] + localElement[0][2][0]) / 2
                    # left of "nm" keyword
                    if(localRightX < rightX):
                        localxDistance = leftX - localRightX
                        # closest to "nm" keyword
                        if(localxDistance < xDistance):
                            valueElement = localElement
                            xDistance = localxDistance
            
            # combine keyword "nm" with the number before it
            element[1] = valueElement[1] + element[1]
            element[0][0] = valueElement[0][0]
            element[0][3] = valueElement[0][3]

    # find the corresponding value for the given "ic50" keyword
    downY = max(position[0][2][1], position[0][3][1])
    topY = min(position[0][0][1], position[0][1][1])
    leftX = (position[0][0][0] + position[0][3][0]) / 2
    rightX = (position[0][1][0] + position[0][2][0]) / 2
    xDistance = position[0][1][0]
    for element in nmArr:
        localCenterY = (element[0][0][1] + element[0][1][1] + element[0][2][1] + element[0][3][1]) / 4
        # same y level as "ic50" keyword
        if(localCenterY <= downY and localCenterY >= topY):
            localLeftX = (element[0][0][0] + element[0][3][0]) / 2
            # right of "ic50" keyword
            if(localLeftX > leftX):
                localxDistance = localLeftX - rightX
                # closest to "ic50" keyword
                if(localxDistance < xDistance):
                    ic50Value = element[1]
                    localxDistance = xDistance

if(ic50Value):
    ic50Value = ic50Value.strip()
    if(ic50Value[0] == "="):
        ic50Value = ic50Value[1:]

# identify all compound names from the abstract image
compoundFound = False
for word in contentResult:
    word = word.lower().strip()
    if(word == "compound"):
        compoundFound = True
        continue
    if("compound" in word):
        pos = word.find("compound")
        pos += 8
        if(pos < len(word) and compoundName(word[pos:])):
            compoundArr.append(word[pos:].strip())
    if(compoundFound):
        if(compoundName(word)):
            compoundArr.append(word)
        compoundFound = False

if(len(moleculeArr) > 0):
    molecule = moleculeArr[-1]
if(len(compoundArr) > 0):
    compound = compoundArr[-1]

moleculeArr.clear()
compoundArr.clear()
ic50Arr.clear()

# identify all compound names and ic50 values from abstract text
compoundFound = False
ic50Found = False
for word in abstractText.split():
    word = word.lower().strip()
    if("compound" in word):
        compoundFound = True
        continue
    if(compoundFound):
        if(compoundName(word)):
            compoundArr.append(word)
        compoundFound = False
    
    if(ic50(word)):
        ic50Found = True
    if(ic50Found):
        ic50Arr.append(word)
        if("nm" in word):
            ic50Found = False


print(molecule)
print(moleculeArr)
print(compound)
print(compoundArr)
print(ic50Value)
print(ic50Arr)


