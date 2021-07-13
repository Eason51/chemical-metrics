import requests
from html.parser import HTMLParser
import sys

keyWords = []

for i in range(1, len(sys.argv)):
    keyWords.append(sys.argv[i])

fileId = 0

with open(f"files/{keyWords[0]}/file{fileId}.html", "w", encoding="utf-8") as outputFile:
    
    class TableParser(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.HTML = ""

            self.ICFound = False
            self.keywordFound = False
            self.abstractFound = False
            self.paragraphFound = False
            self.paragraphDivCount = 0

        
        
        def handle_starttag(self, tag, attrs):
            self.HTML += (self.get_starttag_text())

            if(self.keywordFound):
                return
            
            if(tag == "p" and len(attrs) == 1 and attrs[0][1] == "articleBody_abstractText"):
                self.abstractFound = True
            if(tag == "div" and len(attrs) == 1 and "NLM_p" in attrs[0][1]):
                self.paragraphFound = True
                self.paragraphDivCount += 1
            elif(self.paragraphFound and tag == "div"):
                self.paragraphDivCount += 1
        
        
        
        def handle_data(self, data):
            self.HTML += (data)

            if(self.keywordFound):
                return

            if(self.paragraphFound or self.abstractFound):
                stringList = ["ic50", "ec50", "ki50", "kd50", "ed50"]            
                if(any(substring in data.lower().strip() for substring in stringList)):
                    self.keywordFound = True
                elif(self.ICFound):
                    if(len(data) >= 2 and data[:2] == "50"):
                        self.keywordFound = True
                    else:
                        self.ICFound = False
                elif(len(data) >= 2 and (data.lower().strip()[-2:] in ["ic", "ec", "ki", "kd", "ed"])):
                    self.ICFound = True
        
        
        
        def handle_endtag(self, tag):
            self.HTML += (f"</{tag}>")

            if(self.keywordFound):
                return

            if(self.abstractFound and tag == "p"):
                self.abstractFound = False
            if(self.paragraphFound and tag == "div" and self.paragraphDivCount == 1):
                self.paragraphFound = False
                self.paragraphDivCount -= 1
            elif(self.paragraphFound and tag == "div" and self.paragraphDivCount > 1):
                self.paragraphDivCount -= 1



    with open("test.html", encoding="utf-8") as inputFile:
        tableParser = TableParser()
        tableParser.feed(inputFile.read())
        
        if(tableParser.keywordFound):
            outputFile.write(tableParser.HTML)
        else:
            print("fault")
