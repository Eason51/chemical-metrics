from html.parser import HTMLParser
from chemdataextractor import Document
import easyocr
from torch._C import ConcreteModuleTypeBuilder

TARGET = "janus kinase"
fileId = 6
DOMAIN = "https://pubs.acs.org"

titleText = ""
imgArr = []
abstractText = ""

moleculeArr = []
compoundArr = []
ic50Arr = []

molecule = ""
compound = ""
ic50Value = ""

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

def compoundName(string):
    if(string == ""):
        return False
    string = string.lower().strip()
    if(string.isdigit()):
        return True
    if(len(string) >= 2 and string[:-1].isdigit() and string[-1].isalpha()):
        return True


with open(f"files/{TARGET}/file{fileId}.html", encoding="utf-8") as inputFile:

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

    tableParser = TableParser()
    tableParser.feed(inputFile.read())

    imgArr = tableParser.imgArr
    abstractText = tableParser.abstractText

doc = Document(titleText)
for NR in doc:
    moleculeArr.append(NR.cems[0])

reader = easyocr.Reader(["en"], gpu = False)
# retrieve picture through http request
positionResult = reader.readtext("img.jpg")
contentResult = reader.readtext("img.jpg", detail = 0)


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
    
    if("=" in word and "nm" in word):
        ic50Arr.append(word)

if(len(moleculeArr) > 0):
    molecule = moleculeArr[-1]
if(len(compoundArr) > 0):
    compound = compoundArr[-1]
if(len(ic50Arr) > 0):
    ic50Value = ic50Arr[-1]

moleculeArr.clear()
compoundArr.clear()
ic50Arr.clear()

compoundFound = False
ic50Found = False
for word in abstractText.split():
    word = word.lower().strip()
    if("compound" in word):
        compoundFound = True
        continue
    if(compoundFound):
        print(word)
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


