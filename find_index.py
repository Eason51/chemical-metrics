import json
import requests
from html.parser import HTMLParser
import glob
from elsapy.elsclient import ElsClient
from elsapy.elsdoc import FullDoc

# mind capital vs lower case

def exitParser(parser):
    parser.reset()

class ACSParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)

        self.titleFound = False
        self.titleText = False
        self.title = ""

        self.abstractText = ""
        self.abstractFound = False
        self.textFound = False
    
    def handle_starttag(self, tag, attrs):

        if (tag == "h1" and len(attrs) == 1 and attrs[0][1] == "article_header-title"):
            self.titleFound = True
        if(self.titleFound and tag == "span"):
            self.titleText = True
        
        if (tag == "div" and len(attrs) == 1 and attrs[0][1] == "article_content"):
            self.abstractText += " . "
            self.abstractFound = False
            exitParser(self)
        if (tag == "div" and len(attrs) >= 1):
            for attr in attrs:
                if (attr[0] == "class" and attr[1] == "article_abstract-content hlFld-Abstract"):
                    self.abstractFound = True
                    break
        if (self.abstractFound and tag == "p" and len(attrs) == 1 and attrs[0][1] == "articleBody_abstractText"):
            self.textFound = True

    
    def handle_data(self, data):

        if(self.titleText):
            self.title += data
        if(self.textFound):
            self.abstractText += data
    
    def handle_endtag(self, tag):

        if(self.titleFound and tag == "h1"):
            self.titleFound = False
        if(self.titleText and tag == "span"):
            self.titleText = False
        if(self.textFound and tag == "p"):
            self.textFound = False


def find_acs_article_list(target):

    articleURLArr = []

    for fileId in range(len(glob.glob(f"files/{target.lower()}/*"))):
        with open(f"files/{target.lower()}/file{fileId}.html", encoding="utf-8") as inputFile:
            parser = ACSParser()
            try:
                parser.feed(inputFile.read())
            except AssertionError:
                pass

            if(target in parser.title):
                articleURLArr.append(fileId)
                continue
            elif(target in parser.abstractText):
                articleURLArr.append(fileId)
    
    return articleURLArr





class ScienceDirectParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        
        self.titleFound = False
        self.titleText = ""

        self.abstractTextFound = False
        self.abstractTextContent = False
        self.abstractText = ""

        self.title = ""

        self.keywordArr = []
        self.keywordFound = False
        self.keywordText = False




    def handle_starttag(self, tag, attrs):

        if(tag == "body"):
            exitParser(self)
        if(tag == "ce:title"):
            self.titleFound = True
        if(tag == "ce:abstract"):
            for attr in attrs:
                if(attr[0] == "class" and attr[1] == "author"):
                    self.abstractTextFound = True
                    return
        if(self.abstractTextFound and tag == "ce:simple-para"):
            self.abstractTextContent = True  
        if(tag == "ce:keywords"):
            self.keywordFound = True     
        if(self.keywordFound and tag == "ce:text"):
            self.keywordText = True 


    def handle_data(self, data):
        
        if(self.titleFound):
            self.titleText = data
            self.title = data
        if(self.abstractTextContent):
            self.abstractText += data
        if(self.keywordText):
            self.keywordArr.append(data)


    def handle_endtag(self, tag):

        if(self.titleFound and tag == "ce:title"):
            self.titleFound = False
        if(self.abstractTextFound and tag == "ce:abstract"):
            self.abstractTextFound = False
        if(self.abstractTextContent and tag == "ce:simple-para"):
            self.abstractTextContent = False
        if(self.keywordFound and tag == "ce:keywords"):
            self.keywordFound = False
        if(self.keywordText and tag == "ce:text"):
            self.keywordText = False



con_file = open("config.json")
config = json.load(con_file)
con_file.close()
APIKEY = config['apikey']

def check_sciencedirect_article(doi, target):

    QUERY_URL = "https://api.elsevier.com/content/article/doi/"
    header = {"X-ELS-APIKey": APIKEY, "Accept": "text/xml"}
    response = requests.get(QUERY_URL + doi, headers=header)

    parser = ScienceDirectParser()
    try:
        parser.feed(response.text)
    except AssertionError:
        pass

    if(target in parser.title):
        return True
    for keyword in parser.keywordArr:
        if(target in keyword):
            return True
    if(target in parser.abstractText):
        return True

    return False





            







