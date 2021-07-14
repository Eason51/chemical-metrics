from re import L
import requests
from html.parser import HTMLParser
from chemdataextractor import Document
import easyocr


TARGET = "janus kinase"
fileId = 6
DOMAIN = "https://pubs.acs.org"


# fullname and abbreviation is used in ic50 extraction in abstract image
# stores the fullname of the target gene, omit number, e.g. if target is "jak1", fullname is "janus kinase"
FULLNAME = ""
# stores the abbreviation of the target gene, omit number, e.g. if target is "jak1", abbreviation is "jak"
ABBREVIATION = ""

focusedTarget = ""


# hold title content after parsing html file
titleText = ""
# hold links to abstract images after parsing html file
imgArr = []
# hold abstract content after parsing html file
abstractText = ""

# BodyText object for holding body text
bodyText = None
# Table object for holding tables
tables = None



# hold the molecule name
molecule = ""
# hold the compound name
compound = ""
# hold the ic50 value
ic50Value = ""

# Arr variables provide additional and alternative information, in case the identified molecule, compound, ic50value are incorrect

# hold all identified molecule names
moleculeArr = []
# hold all identified compound names
compoundArr = []
# hold all identified ic50 values
ic50Arr = []


# Classes for holding the content and structure of body text and tables

class BodyText:
    
    class Section:
        
        class Paragraph:
            def __init__(self, header = ""):
                self.header = header
                self.contents = [] # list[str]
        
        def __init__(self, title):
            self.title = title
            self.paragraphs = [] # list[self.Paragraph]
    
    def __init__(self):
        self.sections = [] # list[self.Section]


class Table:

    class Grid:

        class Row:

            def __init__(self):
                # a cell may hold empty string, if html element is "&nbsp"
                self.cells = [] # list[str]

        def __init__(self):
            self.columnNum = 0
            self.header = [] # list[self.Row]
            self.body = [] # list[self.Row]

    def __init__(self):
        self.caption = ""
        self.descriptions = [] # list[str]
        self.grid = self.Grid()



# Parsers cannot exit from inside, the reset() method needs to be called from outside
def exitParser(parser):
    parser.reset()

# identify whether a string is "ic50", OCR result could be "icso", "icSo" etc.
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

# identify whether a string is in the form of a compound name, pure number like 18, or number followed by letter like 18ae
def compoundName(string):
    if(string == ""):
        return False
    string = string.lower().strip()
    if(string.isdigit()):
        return True
    if(len(string) >= 2 and string[0].isdigit()):
        onlyDigit = True
        for c in string:
            if(not onlyDigit and not c.isalpha()):
                return False
            if(onlyDigit and not c.isdigit()):
                onlyDigit = False
        return True
    return False

# identify whether a string is in the form of a molecule name, either pure letters, or contains numbers with dash("-")
def moleculeName(string):
    string = string.lower().strip()
    if(string.isalpha()):
        return True
    hasNumber = False
    hasDash = False
    for letter in string:
        if(letter.isdigit()):
            hasNumber = True
        elif(letter == "-"):
            hasDash = True
    if(hasNumber and not hasDash):
        return False
    return True






# find FULLNAME and ABBREVIATION of TARGET
# --------------------------------------------------------------------------------------------------------------

# trim the number at the end of TARGET
i = len(TARGET) - 1
while(i >= 0):
    if(not TARGET[i].isalpha()):
        i -= 1
    else:
        break
queryTarget = TARGET[:i + 1]

# target name identification is performed through an online database: http://allie.dbcls.jp/
# at this point, the user might input a fullname or an abbreviation, so it needs to be queried twice

# queryLongUrl: treat the input as a fullname, find abbreviation
queryLongUrl = f"https://allie.dbcls.jp/long/exact/Any/{queryTarget.lower()}.html"
# queryShortUrl: treat the input as an abbreviation, find fullname
queryShortUrl = f"https://allie.dbcls.jp/short/exact/Any/{queryTarget.lower()}.html"

longResponse = requests.get(queryLongUrl)
shortReponse = requests.get(queryShortUrl)



# Parse the reponse from online enquiry and store useful information
class TargetParser(HTMLParser):
    def __init__(self, ):
        HTMLParser.__init__(self)

        self.tableFound = False
        self.resultFound = False
        # the returned abbreviation or full name
        self.result = ""
        self.columnNum = 0
        self.frequencyFound = False
        # frequency of occurrence of self.result found in database
        self.frequency = 0

    
    def handle_starttag(self, tag, attrs):
        if(tag == "table"):
            self.tableFound = True
        if(tag == "table" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "sortable"):
                    self.resultFound = True
        if(self.resultFound and tag == "td"):
            self.columnNum += 1
        if(self.columnNum == 2 and tag == "div"):
            exitParser(self)
        if(self.columnNum == 2 and tag == "br"):
            self.frequencyFound = True

    
    def handle_data(self, data):
        if(self.frequencyFound):
            frequencyStr = ""
            for c in data:
                if(c.isdigit()):
                    frequencyStr += c
            self.frequency = int(frequencyStr)
            return
        if(self.columnNum == 2):
            self.result += data
        if(self.tableFound):
            if("not found" in data):
                exitParser(self)

    
    def handle_endtag(self, tag):
        if(self.resultFound and tag == "table"):
            self.resultFound = False
        if(self.tableFound and tag == "table"):
            self.tableFound = False


longParser = TargetParser()
shortParser = TargetParser()
try:
    longParser.feed(longResponse.text)    
except AssertionError as ae:
    pass

try:
    shortParser.feed(shortReponse.text)
except AssertionError as ae:
    pass

longForm = shortParser.result.lower().strip()
longFrequency = shortParser.frequency
shortForm = longParser.result.lower().strip()
shortFrequency = longParser.frequency

# if the input is a full name, shortFrequency will be 0, the input will be FULLNAME, vice versa.
if(shortFrequency > longFrequency):
    FULLNAME = queryTarget
    ABBREVIATION = shortForm
else:
    FULLNAME = longForm
    ABBREVIATION = queryTarget






# parsing a html file
# --------------------------------------------------------------------------------------------------------------

class TableParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)

        # enable this flag to skip handle_data for the next element
        self.disableRead = False

        # the link(s) to access abstract image
        self.imgArr = []
        # complete abstract text content
        self.abstractText = ""
        # all elements in abstract text in bold (<b></b>)
        self.boldAbstractTextArr = []

        self.abstractFound = False
        self.figureFound = False
        self.imgLinkFound = False
        self.textFound = False
        self.boldTextFound = False

        self.titleFound = False
        self.titleText = False

        # a BodyText object to hold the content of body text
        self.bodyText = BodyText()
        self.newSectionFound = False
        self.sectionTitleFound = False
        self.paragraphFound = False
        self.paragraphDivCount = 0
        # hold the content of the paragraph currently being parsed
        self.paragraphText = ""
        self.paragraphHeaderFound = False
        # hold the title for the currently parsed paragraph (could be empty)
        self.paragraphHeader = ""

        # hold all the Table objects contained in the current article
        self.tables = [] # list[Table]
        self.tableFound = False
        self.tableDivCount = 0
        self.tableCaptionFound = False
        self.tableCaptionDivCount = 0
        # hold the caption of the table currently being parsed
        self.tableCaption = ""

        self.tableGridFound = False
        self.tableColCountFound = False
        self.gridHeaderFound = False
        self.cellFound = False
        self.gridBodyFound = False
        # hold the content of the current parsing cell
        self.cell = ""
        self.cellSpace = False

        self.tableDescriptionFound = False
        self.tableDescriptionDivCount = 0
        self.tableFootnoteFound = False
        


    def handle_starttag(self, tag, attrs):
        
        # handle title, abstract image and abstract text

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
        if(self.textFound and tag == "b"):
            self.boldTextFound = True

        #handle body text
        
        if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content-title"):
            self.sectionTitleFound = True
            self.newSectionFound = True
        if(tag == "div" and len(attrs) == 1 and "NLM_p" in attrs[0][1]):
            self.paragraphFound = True
            self.paragraphDivCount += 1
        elif(self.paragraphFound and tag == "div"):
            self.paragraphDivCount += 1
        if(tag == "h3" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "article-section__title"):
                    self.paragraphHeaderFound = True

        # handle table caption
        
        if(tag == "div" and len(attrs) > 1):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "NLM_table-wrap"):
                    self.tableFound = True
                    self.tableDivCount += 1
                    self.tables.append(Table())
                    return
        if(self.tableFound and tag == "div"):
            self.tableDivCount += 1
        if(self.tableFound and tag == "div" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "NLM_caption"):
                    self.tableCaptionFound = True
                    self.tableCaptionDivCount += 1
                    return
        if(self.tableCaptionFound and tag == "div"):
            self.tableCaptionDivCount += 1
        if(self.tableCaptionFound and tag == "a"):
            self.disableRead = True
        
        # handle table grid
        
        if(self.tableFound and tag == "table"):
            self.tableGridFound = True
        if(self.tableGridFound and tag == "colgroup"):
            self.tableColCountFound = True
        if(self.tableColCountFound and tag == "col"):
            self.tables[-1].grid.columnNum += 1
        if(self.tableGridFound and tag == "thead"):
            self.gridHeaderFound = True
        if(self.gridHeaderFound and tag == "tr"):
            self.tables[-1].grid.header.append(Table.Grid.Row())
        if(self.gridHeaderFound and tag == "th"):
            self.cellFound = True
        if(self.tableGridFound and tag == "tbody"):
            self.gridBodyFound = True
        if(self.gridBodyFound and tag == "tr"):
            self.tables[-1].grid.body.append(Table.Grid.Row())
        if(self.gridBodyFound and tag == "td"):
            self.cellFound = True
        if(self.cellFound and tag == "sup"):
            self.cellSpace = True
        if(self.cellFound and tag == "br"):
            self.cell += " "
        
        # handle table description
        
        if(self.tableFound and (not self.tableCaptionFound) and (not self.tableGridFound) and tag == "div" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "NLM_table-wrap-foot"):
                    self.tableDescriptionFound = True
                    self.tableDescriptionDivCount += 1
                    return
        if(self.tableDescriptionFound and tag == "div"):
            self.tableDescriptionDivCount += 1
        if(self.tableDescriptionFound and tag == "div" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "footnote"):
                    self.tableFootnoteFound = True
                    self.tables[-1].descriptions.append("")
        if(self.tableFootnoteFound and tag in ["sup", "a"]):
            self.disableRead = True



    def handle_data(self, data):
        if(self.disableRead):
            return
        if(self.cellSpace):
            self.cell += " "
            return

        # handle title and abstract

        if(self.textFound):
            self.abstractText += data
        if(self.titleText):
            global titleText
            titleText += data
        if(self.boldTextFound):
            self.boldAbstractTextArr.append(data)
        
        # handle body text

        # found a new section, append the section to bodyText
        if(self.newSectionFound):
            section = BodyText.Section(data)
            self.bodyText.sections.append(section)
            self.newSectionFound = False
            # ignore any content after references
            if(data == "References"):
                exitParser(self)
        if(self.paragraphFound):
            self.paragraphText += data
        if(self.paragraphHeaderFound):
            self.paragraphHeader += data

        # handle Tables

        if(self.tableCaptionFound):
            self.tableCaption += data
        if(self.gridHeaderFound and self.cellFound):
            self.cell += data            
        if(self.gridBodyFound and self.cellFound):
            self.cell += data
        if(self.tableFootnoteFound):
            self.tables[-1].descriptions[-1] += data

    
    def handle_endtag(self, tag):
       
        # handle title and abstract
        
        if(self.disableRead):
            self.disableRead = False
        if(self.cellSpace):
            self.cellSpace = False
        if(self.figureFound and tag == "figure"):
            self.figureFound = False
        if(self.textFound and tag == "p"):
            self.textFound = False
        if(self.titleFound and tag == "h1"):
            self.titleFound = False
        if(self.titleText and tag == "span"):
            self.titleText = False
        if(self.boldTextFound and tag == "b"):
            self.boldTextFound = False
        
        # handle body text
        
        if(self.sectionTitleFound and tag == "div"):
            self.sectionTitleFound = False
        # found the end of a paragraph, append the content to the last section
        if(self.paragraphFound and tag == "div" and self.paragraphDivCount == 1):
            if(len(self.bodyText.sections[-1].paragraphs) == 0):
                newParagraph = BodyText.Section.Paragraph()
                self.bodyText.sections[-1].paragraphs.append(newParagraph)
            self.bodyText.sections[-1].paragraphs[-1].contents.append(self.paragraphText)
            self.paragraphText = ""
            self.paragraphFound = False
            self.paragraphDivCount -= 1
        elif(self.paragraphFound and tag == "div" and self.paragraphDivCount > 1):
            self.paragraphDivCount -= 1
        # found a paragraph header, append a new paragraph with header to the last section
        if(self.paragraphHeaderFound and tag == "h3"):
            self.paragraphHeaderFound = False
            newParagraph = BodyText.Section.Paragraph(self.paragraphHeader)
            self.bodyText.sections[-1].paragraphs.append(newParagraph)
            self.paragraphHeader = ""
        
        # handle table caption

        if(self.tableFound and tag == "div" and self.tableDivCount == 1):
            self.tableFound = False
            self.tableDivCount -= 1
        elif(self.tableFound and tag == "div" and self.tableDivCount > 1):
            self.tableDivCount -= 1
        if(self.tableCaptionFound and tag == "div" and self.tableCaptionDivCount == 1):
            self.tableCaptionFound = False
            self.tableCaptionDivCount -= 1
            self.tables[-1].caption = self.tableCaption
            self.tableCaption = ""
        elif(self.tableCaptionFound and tag == "div" and self.tableCaptionDivCount > 1):
            self.tableCaptionDivCount -= 1
        
        # handle table grip

        if(self.tableGridFound and tag == "table"):
            self.tableGridFound = False
        if(self.tableColCountFound and tag == "colgroup"):
            self.tableColCountFound = False
        if(self.gridHeaderFound and tag == "thead"):
            self.gridHeaderFound = False
        if(self.gridHeaderFound and tag == "th" and self.cellFound):
            self.tables[-1].grid.header[-1].cells.append(self.cell)
            self.cell = ""
            self.cellFound = False
        if(self.gridBodyFound and tag == "tbody"):
            self.gridBodyFound = False
        if(self.gridBodyFound and tag == "td" and self.cellFound):
            self.tables[-1].grid.body[-1].cells.append(self.cell)
            self.cell = ""
            self.cellFound = False

        # handle table description

        if(self.tableDescriptionFound and self.tableDescriptionDivCount == 1 and tag == "div"):
            self.tableDescriptionDivCount -= 1
            self.tableDescriptionFound = False
        elif(self.tableDescriptionFound and tag == "div" and self.tableDescriptionDivCount > 1):
            self.tableDescriptionDivCount -= 1
        if(self.tableFootnoteFound and tag == "div"):
            self.tableFootnoteFound = False



tableParser = TableParser()
# open a file locally, should be retrieved through http request in real programs
with open(f"files/{TARGET}/file{fileId}.html", encoding="utf-8") as inputFile:

    # parse the given html file with TableParser()
    try:
        tableParser.feed(inputFile.read())
    except AssertionError as ae:
        pass

    imgArr = tableParser.imgArr
    abstractText = tableParser.abstractText
    bodyText = tableParser.bodyText
    tables = tableParser.tables




# retrieve target information
# -------------------------------------------------------------------------------------------------------------- 

# find occurrences of target fullname and abbreviation in title
number = ""
fullIndex = titleText.lower().rfind(FULLNAME)
abbrIndex = titleText.lower().rfind(ABBREVIATION)
# find the number following the target name, e.g. "jak3", find "3" after "jak"
if(fullIndex == -1 and abbrIndex == -1):
    pass
# if only fullname is found
elif(fullIndex != -1 and (fullIndex + len(FULLNAME) + 1) < len(titleText)):    
    index = fullIndex + len(FULLNAME) + 1
    while(titleText[index].isdigit()):
        number += titleText[index]
        index += 1
# if only abbreviation is found
elif(abbrIndex != -1 and (abbrIndex + len(FULLNAME) + 1) < len(titleText)):
    index = abbrIndex + len(ABBREVIATION) + 1
    while(titleText[index].isdigit()):
        number += titleText[index]
        index += 1
# of both fullname and abbreviation are found
elif((fullIndex + len(FULLNAME) + 1) < len(titleText) and (abbrIndex + len(ABBREVIATION) + 1) < len(titleText)):
    # abbreviation is preferred over fullname
    index = abbrIndex + len(ABBREVIATION) + 1
    while(titleText[index].isdigit()):
        number += titleText[index]
        index += 1
    if(not number):
        index = fullIndex + len(FULLNAME) + 1
        while(titleText[index].isdigit()):
            number += titleText[index]
            index += 1

# use abbreviation and the identfied number as the target name to look for in the image
if(number):
    focusedTarget = ABBREVIATION + number

# if targetname is not found in the title, search in the abstract text
if(not focusedTarget):
    targetArr = []

    # find every full target name in the abstract text, record its frequency and last occurred position
    index = 0
    while(index >= 0 and index < len(abstractText)):
        index = abstractText.lower().find(FULLNAME, index)
        if(index != -1 and (index + len(FULLNAME) + 1) < len(abstractText)):
            number = ""
            index += len(FULLNAME) + 1
            while(index < len(abstractText)):
                if(abstractText[index].isdigit()):
                    number += abstractText[index]
                    index += 1
                else:
                    break
            if(number):
                targetName = ABBREVIATION + number
                targetFound = False
                for freqPosTarget in targetArr:
                    if(freqPosTarget[2] == targetName):
                        freqPosTarget[0] += 1
                        freqPosTarget[1] = index
                        targetFound = True
                        break
                if(not targetFound):
                    targetArr.append([1, index, targetName])
        elif(index != -1):
            index += 1
                

    # find every abbreviatioin target name in the abstract text, record its frequency and last occurred position
    index = 0
    while(index >= 0 and index < len(abstractText)):
        index = abstractText.lower().find(ABBREVIATION, index)
        if(index != -1 and (index + len(ABBREVIATION) < len(abstractText))):
            number = ""
            index += len(ABBREVIATION)
            while(index < len(abstractText)):
                if(abstractText[index].isdigit()):
                    number += abstractText[index]
                    index += 1
                else:
                    break
            if(number):
                targetName = ABBREVIATION + number
                targetFound = False
                for freqPosTarget in targetArr:
                    if(freqPosTarget[2] == targetName):
                        freqPosTarget[0] += 1
                        freqPosTarget[1] = index
                        targetFound = True
                        break
                if(not targetFound):
                    targetArr.append([1, index, targetName])
        elif(index != -1):
            index += 1        
        
    #sort target names first by frequency, then by last occured position
    if(len(targetArr) > 0):
        targetArr.sort(reverse=True)
        focusedTarget = targetArr[0][2]






# process image information
# --------------------------------------------------------------------------------------------------------------  


# identify all text within the abstract image
reader = easyocr.Reader(["en"], gpu = False)
# retrieve picture through http request
positionResult = reader.readtext(f"images/{TARGET}/image{fileId}.jpeg")


# identify the ic50 value from abstract image

# find ic50 keyword location
xrangeArr = []
elements = []
for element in positionResult:
    if(ic50(element[1].lower()) or ("ic" in element[1].lower() and "nm" in element[1].lower())):
        elements.append(element)
        leftX = min(element[0][0][0], element[0][3][0])
        rightX = max(element[0][1][0], element[0][2][0])
        xrangeArr.append([leftX, rightX, element[1]])        


# find the rightmost ic50 keyword
needTarget = False
position = []
centerX = 0
for element in elements:
    if(needTarget):
        break
    
    localCenterX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
    for range in xrangeArr:
        if(localCenterX >= range[0] and localCenterX <= range[1] and element[1] != range[2]):
            needTarget = True
            break
    if(localCenterX > centerX):
        centerX = localCenterX
        position = element


if((not needTarget) and len(position) > 0):
    # check if ic50 keyword contains the required value
    valueFound = False
    for word in position[1].lower().split():
        if("nm" in word):
            valueFound = True
            break

    # if ic50 keyword contains the value, retrieve the value
    if(valueFound):
        pos = position[1].find("=")
        if(pos == -1):
            pos = position[1].find(":")
        if(pos == -1 or (pos + 1) >= len(position[1])):
            valueFound = False
        else:
            ic50Value = position[1][pos + 1: ]

    # if no value is found in ic50 keyword
    else:
        # find all keywords conataining "nm"
        nmArr = []
        for element in positionResult:
            # the "nm" keyword has to locate on the right of "ic50" keyword
            if("nm" in element[1].lower() and (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4 >= min(position[0][1][0], position[0][2][0])):
                nmArr.append(list(element))
                nmArr[0][1] = nmArr[0][1].lower()
        
        for element in nmArr:
            # if the keyword contains only "nm", needs to combine it with the number before it e.g.: keyword(50), keyword(nm), combined into keyword(50nm)
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

        # find the corresponding value for the given "ic50" keyword, e.g. "ic50 = 12nm", find keyword(12nm) on the right of "ic50"
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
        if(ic50Value[0] in ["=", ":"]):
            ic50Value = ic50Value[1:]



# if multiple ic50 values exist for one compound, need to use target name to identify
if((not ic50Value) and focusedTarget):
    targetArr = []

    # find all tokens containing target name
    for element in positionResult:
        if(focusedTarget in element[1].lower()):
            centerX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
            targetArr.append([centerX, element])

    # sort with the rightmost first
    targetArr.sort(reverse=True)

    if(len(targetArr) > 0):
        for target in targetArr:
            targetElement = target[1]

            # if the value is already contained in the token
            if(":" in targetElement[1] or "=" in targetElement[1]):
                hasDigit = False
                for c in targetElement[1]:
                    if(c.isdigit()):
                        hasDigit = True
                        break
                if(hasDigit):
                    ic50Value = targetElement[1]
                    break

            centerX = targetArr[0][0]
            topY = min(targetElement[0][0][1], targetElement[0][1][1])
            downY = max(targetElement[0][2][1], targetElement[0][3][1])

            # find all tokens to the right of the target name
            elementArr = []
            for element in positionResult:
                localCenterX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
                if(localCenterX > centerX):
                    localCenterY = (element[0][0][1] + element[0][1][1] + element[0][2][1] + element[0][3][1]) / 4
                    if(localCenterY >= topY and localCenterY <= downY):
                        elementArr.append([localCenterX, element])
            
            # arrange the identified tokens from left to right, append them all into a string
            elementArr.sort()
            if(len(elementArr) > 0):
                identifiedString = targetElement[1]
                for element in elementArr:
                    identifiedString += element[1][1]
                    index = identifiedString.find("=")
                    if(index == -1):
                        index = identifiedString.find(":")
                    if(index != -1 and (index + 1) < len(identifiedString)):
                        ic50Value = identifiedString[index :]
                    else:
                        ic50Value = identifiedString
                    

                    if(":" not in ic50Value and "=" not in ic50Value):
                        ic50Value = ""
                    
            # if the rightmost target name has no value, check the target names on its left
            if(ic50Value):
                break





# identify all compound names from the abstract image
contentResult = []
for element in positionResult:
    contentResult.append(element[1])
compoundFound = False
# identify all "compound" keyword and the name after it
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

if(len(compoundArr) == 1):
    compound = compoundArr[0]


if(not compound):
    compoundPosArr = []
    # find all keyword in the form of a compound name
    for element in positionResult:
        if(compoundName(element[1]) and "nm" not in element[1].lower()):
            compoundPosArr.append(element)
    
    # find the centerX of all identified keyword
    tempArr = []
    for element in compoundPosArr:
        centerX = (element[0][0][0] + element[0][1][0] + element[0][2][0] + element[0][3][0]) / 4
        tempArr.append([centerX, element[1]])
    tempArr.sort(reverse=True)

    # use the rightmost keyword as compound name
    if(len(tempArr) > 0):
        compound = tempArr[0][1]


compoundArr.clear()
ic50Arr.clear()


# process text information
# --------------------------------------------------------------------------------------------------------------

# find all identified molecule names inside of title
doc = Document(titleText)
for NR in doc.cems:
    moleculeArr.append(NR.text)
tempArr = []
for name in moleculeArr:
    if(moleculeName(name)):
        tempArr.append(name)
moleculeArr = tempArr # moleculeArr contains all chemistry named entities found in the title

if(len(moleculeArr) == 1):
    molecule = moleculeArr[0]
    moleculeArr.clear()
else:
    # if there's multiple named entities in title, then use abstract text to help identification
    titleMoleculeArr = moleculeArr.copy()
    moleculeArr.clear()
    
    doc = Document(abstractText)
    for NR in doc.cems:
        moleculeArr.append(NR.text)
    textArr = []
    for name in moleculeArr:
        if(moleculeName(name)):
            textArr.append(name)
    
    if(len(titleMoleculeArr) == 0):
        moleculeArr = textArr.copy()
    elif(len(textArr) == 0):
        moleculeArr = titleMoleculeArr.copy()
    else:
        # find named entities that appear both in title and in abstract text
        moleculeArr = list(set(titleMoleculeArr).intersection(textArr))
        if(len(moleculeArr) == 0):
            moleculeArr = titleMoleculeArr.copy()
    
    if(len(moleculeArr) == 1):
        molecule = moleculeArr[0]




# identify compound name from abstract text, comppound names are always in bold ( <b>keyword</b> )
compoundArr = tableParser.boldAbstractTextArr.copy()
# find all keywords in the form of compound name
tempArr = []
for name in compoundArr:
    if(compoundName(name)):
        tempArr.append(name)

# find the frequency of occurrence of each keyword in abstract text
compoundArr.clear()
for name in tempArr:
    nameFound = False
    for freqName in compoundArr:
        if(freqName[1] == name):
            freqName[0] += 1
            nameFound = True
            break
    if(not nameFound):
        compoundArr.append([1, name])
compoundArr.sort(reverse=True)

tempArr.clear()
if(len(compoundArr) > 0):
    # find all keywords with the highest frequency of occurrence
    maxFreq = compoundArr[0][0]
    for freqName in compoundArr:
        if(freqName[0] == maxFreq):
            tempArr.append([-1, freqName[1]])
    
    # find the position where the keyword is in abstract text
    # if there are multiple keywords have the highest frequency, select the one occurs last in text
    for posName in tempArr:
        position = len(tableParser.boldAbstractTextArr) - 1
        while(position >= 0):
            if(tableParser.boldAbstractTextArr[position] == posName[1]):
                posName[0] = position
                break
            position -= 1
    
    tempArr.sort(reverse=True)
    compoundArr = tempArr.copy()



# identify all ic50 values from abstract text
compoundFound = False
ic50Found = False
for word in abstractText.split():
    word = word.lower().strip()
    
    if(ic50(word)):
        ic50Found = True
        ic50Arr.append("")
    if(ic50Found):
        ic50Arr[-1] += (word + " ")
        if("nm" in word):
            ic50Found = False


print(molecule)
print(moleculeArr)
print(compound)
print(compoundArr)
print(ic50Value)
print(ic50Arr)




