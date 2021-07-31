import requests
from html.parser import HTMLParser

def exitParser(parser):
    parser.reset()

class ImageParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)

        self.abstractFound = False
        self.imgURL = ""
    
    def handle_starttag(self, tag, attrs):
        
        if(tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_abstract"):
            self.abstractFound = True
        if(self.abstractFound and tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content"):
            self.abstractFound = False
        if(self.abstractFound and tag == "a"):
            title = ""
            link = ""
            for attr in attrs:
                if(attr[0] == "title"):
                    title = attr[1]
                if(attr[0] == "href"):
                    link = attr[1]
            if(title == "High Resolution Image"):
                self.imgURL = "https://pubs.acs.org/" + link

target = "egfr"

for i in range(4):
    tableParser = ImageParser()
    with open(f"files/{target}/file{i}.html", encoding="utf-8") as inputFile:
        try:
            tableParser.feed(inputFile.read())
        except AssertionError as ae:
            pass

        if(tableParser.imgURL):
            image = requests.get(tableParser.imgURL).content
            with open(f"images/{target}/image{i}.jpeg", "wb") as handler:
                handler.write(image)

    


