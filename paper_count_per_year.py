from re import L
import requests
from html.parser import HTMLParser
import json

# 药理（即list中的第二个数值）
# Nature Reviews Drug Discovery
def get_NRD (keyword):
    if ' ' in keyword:
        keyword = keyword.replace(' ', '%20')
    base_url = 'https://www.nature.com/search?q=' + keyword + '&journal=nrd'

    headers = {
        'Accept': 'text/html',
        'User-agent': 'Mozilla/5.0'
    }
    r = requests.get(base_url, stream=True, headers=headers, timeout=30)
    return r


# Journal of Pharmacology and Experimental Therapeutics
def get_JPET (keyword):
    if ' ' in keyword:
        keyword = keyword.replace(' ', '%252B')
    base_url = 'https://jpet.aspetjournals.org/search/'+ keyword + '%20jcode%3Ajpet%20numresults%3A10%20sort%3Arelevance-rank%20format_result%3Astandard'

    headers = {
        'Accept': 'text/html',
        'User-agent': 'Mozilla/5.0'
    }
    r = requests.get(base_url, stream=True, headers=headers, timeout=30)
    return r



# Advanced Drug Delivery Reviews (SienceDirect)



# 临床 (即list中的第三个数值)
# The New England Journal of Medicine
def get_NEJM (keyword):
    if ' ' in keyword:
        keyword = keyword.replace(' ', '+AND+')
    base_url = 'https://www.nejm.org/search?q='+ keyword + '&asug='

    headers = {
        'Accept': 'text/html',
        'User-agent': 'Mozilla/5.0'
    }
    r = requests.get(base_url, stream=True, headers=headers, timeout=30)
    return r



# The Lancet (SienceDirect)


# The Journal of the American Medical Association
def get_JAMA (keyword):
    if ' ' in keyword:
        keyword = keyword.replace(' ', '%2520')
    base_url = 'https://jamanetwork.com/searchresults?q='+ keyword + '&hd=advancedAll&restypeid=3&fl_JournalDisplayName=JAMA'

    headers = {
        'Accept': 'text/html',
        'User-agent': 'Mozilla/5.0'
    }
    r = requests.get(base_url, stream=True, headers=headers, timeout=30)
    return r



def get_response(url):

    headers = {
        'Accept': 'text/html',
        'User-agent': 'Mozilla/5.0'
    }
    r = requests.get(url, stream=True, headers=headers, timeout=30)
    return r





def exitParser(parser):
    parser.reset()


def get_Amount(firstResponse, ParserCtor):

    parser = ParserCtor()
    try:
        response = firstResponse
        parser.feed(response.text)
    except AssertionError as ae:
        pass
    dateArr = parser.dateArr
    url = parser.nextPageLink

    while(parser.nextPageLink):
        parser = ParserCtor()
        parser.dateArr = dateArr
        try:
            response = get_response(url)
            parser.feed(response.text)
            
        except AssertionError as ae:
            dateArr = parser.dateArr
            url = parser.nextPageLink

    # i = 0
    # for yearCount in dateArr:
    #     i += yearCount[1]
    # print(i)

    dateArr.sort()
    return dateArr


# response = get_JPET("janus kinase")
# print(get_Amount(response, JPETParser))



def get_ScienceDirect_amount(journal, keyword):

    offset = 0
    
    url = "https://api.elsevier.com/content/search/sciencedirect"
    header = {"x-els-apikey": "7f59af901d2d86f78a1fd60c1bf9426a", "Accept": "application/json", "Content-Type": "application/json"}
    payload = {
    "qs": f"{keyword}",
    "pub": f"{journal}",
    "display": {
            "offset": offset,
            "show": 100
        }
    }
    
    dateArr = []
    response = requests.put(url, headers=header, json=payload)
    result = json.loads(response.text)


    while(True):
        if("results" in result and len(result["results"]) > 0):
            for article in result["results"]:
                
                year = article["publicationDate"][:4]
                yearFound = False
                for yearCount in dateArr:
                    if(yearCount[0] == year):
                        yearFound = True
                        yearCount[1] += 1
                        break
                if(not yearFound):
                    dateArr.append([year, 1])
        else:
            break

        offset += 100
        display = {
                "offset": offset,
                "show": 100
            }
        payload = {
        "qs": f"{keyword}",
        "pub": f"{journal}",
        "display": display
        }
        response = requests.put(url, headers=header, json=payload)
        result = json.loads(response.text)

    
    i = 0
    for yearCount in dateArr:
        i += yearCount[1]    

    dateArr.sort()
    return dateArr




class NRDParser(HTMLParser):

    
    def __init__(self):
        HTMLParser.__init__(self)

        self.DOMAIN = "https://www.nature.com"
        self.nextPageLink = ""
        self.dateArr = []
        
        self.dateFound = False
        self.nextPageFound = False

    def handle_starttag(self, tag, attrs):
        
        if(tag == "time" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "itemprop" and attr[1] == "datePublished"):
                    self.dateFound = True
        if(tag == "li" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "data-test" and attr[1] == "page-next"):
                    self.nextPageFound = True
                    return
        if(self.nextPageFound and tag == "a" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "href"):
                    self.nextPageLink = self.DOMAIN + attr[1]
            exitParser(self)
        if(self.nextPageFound and tag == "span" and len(attrs) == 1 and attrs[0][1] == "c-pagination__link c-pagination__link--disabled"):
            exitParser(self)

    
    def handle_data(self, data):
        
        if(self.dateFound):
            if(data):
                year = data.split(" ")[-1].strip()
                
                yearFound = False
                for yearCount in self.dateArr:
                    if(yearCount[0] == year):
                        yearFound = True
                        yearCount[1] += 1
                if(not yearFound):
                    self.dateArr.append([year, 1])


    def handle_endtag(self, tag):
        
        if(self.dateFound and tag == "time"):
            self.dateFound = False





class JPETParser(HTMLParser):

    
    def __init__(self):
        HTMLParser.__init__(self)

        self.DOMAIN = "https://jpet.aspetjournals.org"
        self.nextPageLink = ""
        self.dateArr = []

        self.dateFound = False
        self.nextPageFound = False
        

    def handle_starttag(self, tag, attrs):

        if(tag == "span" and len(attrs) == 1 and attrs[0][1] == "highwire-cite-metadata-date highwire-cite-metadata"):
            self.dateFound = True
        if(tag == "li" and len(attrs) == 1 and attrs[0][1] == "pager-next first last odd"):
            self.nextPageFound = True
            return
        if(self.nextPageFound and tag == "a" and len(attrs) > 0):
            for attr in attrs:
                if(attr[0] == "href"):
                    self.nextPageLink = self.DOMAIN + attr[1]
                    exitParser(self)

    
    def handle_data(self, data):

        if(self.dateFound):
            index = data.find(",")
            if(index != -1):
                date = data[:index]
                year = date.split()[-1].strip()

                yearFound = False
                for yearCount in self.dateArr:
                    if(yearCount[0] == year):
                        yearCount[1] += 1
                        yearFound = True
                if(not yearFound):
                    self.dateArr.append([year, 1])


    def handle_endtag(self, tag):
        
        if(self.dateFound and tag == "span"):
            self.dateFound = False





class NEJMParser(HTMLParser):

    
    def __init__(self):
        HTMLParser.__init__(self)

        self.DOMAIN = "https://www.nejm.org/search"
        self.nextPageLink = ""
        self.dateArr = []

        self.dateFound = False
        self.navigatorFound = False
        self.nextPageFound = False
        

    def handle_starttag(self, tag, attrs):

        if(tag == "em" and len(attrs) == 1 and attrs[0][1] == "m-result__date f-tag"):
            self.dateFound = True
        if(tag == "ul" and len(attrs) == 1 and attrs[0][1] == "m-paginator__prev-next"):
            self.navigatorFound = True
        if(self.navigatorFound and tag == "li"):
            if(len(attrs) == 1 and attrs[0][1] == "s-disabled"):
                exitParser(self)
            else:
                self.nextPageFound = True
                return
        if(self.nextPageFound and tag == "a" and len(attrs) > 0):
            link = ""
            linkFound = False
            for attr in attrs:
                if(attr[0] == "href"):
                    link = self.DOMAIN + attr[1]
                elif(attr[0] == "class" and attr[1] == "a-btn a-btn--simple js__scrollTop"):
                    linkFound = True
            
            if(linkFound and link):
                self.nextPageLink = link
                exitParser(self)
            self.navigatorFound = False

    
    def handle_data(self, data):

        if(self.dateFound):
            if(data):
                year = data.split()[-1].strip()

                yearFound = False
                for yearCount in self.dateArr:
                    if(yearCount[0] == year):
                        yearCount[1] += 1
                        yearFound = True
                if(not yearFound):
                    self.dateArr.append([year, 1])


    def handle_endtag(self, tag):
        
        if(self.dateFound and tag == "em"):
            self.dateFound = False
        if(self.navigatorFound and tag == "ul"):
            self.navigatorFound = False




class JAMAParser(HTMLParser):

    
    def __init__(self):
        HTMLParser.__init__(self)

        self.DOMAIN = "https://jamanetwork.com/searchresults?"
        self.nextPageLink = ""
        self.dateArr = []
        
        self.dateFound = False


    def handle_starttag(self, tag, attrs):

        if((tag == "span" or tag == "div")and len(attrs) == 1 and "--pub-date" in attrs[0][1]):
            self.dateFound = True
        if(tag == "a" and len(attrs) > 0):
            link = ""
            linkFound = False
            for attr in attrs:
                if(attr[0] == "data-url"):
                    link = self.DOMAIN + attr[1]
                elif(attr[0] == "class" and attr[1] == "sr-nav-next al-nav-next"):
                    linkFound = True
            
            if(linkFound and link):
                self.nextPageLink = link
                exitParser(self)

    
    def handle_data(self, data):

        if(self.dateFound):
            if(data):
                year = data.split()[-1].strip()
                yearFound = False
                for yearCount in self.dateArr:
                    if(yearCount[0] == year):
                        yearFound = True
                        yearCount[1] += 1
                        break
                if(not yearFound):
                    self.dateArr.append([year, 1])


    def handle_endtag(self, tag):
        
        if(self.dateFound and (tag == "span" or tag == "div")):
            self.dateFound = False


def merge_three_year_count_arrs(arr1, arr2, arr3):

    indexArr = [0, 0, 0]
    valueArr = [arr1, arr2, arr3] # elem: [ [year, count], ]
    frontValueArr = [None, None, None] #elem: [year, count, arrId]

    mergedArr = []

    while(True):

        valid = False
        for i in range(3):
            if(indexArr[i] < len(valueArr[i])):
                valid = True
                break
        if(not valid):
            break

        for i in range(3):
            if(indexArr[i] >= len(valueArr[i])):
                frontValueArr[i] = [["9999", 9999], i]
            else:
                frontValueArr[i] = [ valueArr[i][indexArr[i]], i ]
        
        frontValueArr.sort()
        if(len(frontValueArr) > 0):
            if(frontValueArr[0][0][0] == "9999"):
                break
            if(len(mergedArr) > 0 and mergedArr[-1][0] == frontValueArr[0][0][0]):
                mergedArr[-1][1] += frontValueArr[0][0][1]
                indexArr[frontValueArr[0][1]] += 1
            else:
                mergedArr.append(frontValueArr[0][0])
                indexArr[frontValueArr[0][1]] += 1
        else:
            break
    
    return mergedArr
        



def get_paper_count_per_year(keyword):

    response = get_NRD(keyword)
    secondValueArr1 = get_Amount(response, NRDParser)

    response = get_JPET(keyword)
    secondValueArr2 = get_Amount(response, JPETParser)

    secondValueArr3 = get_ScienceDirect_amount("Advanced Drug Delivery Reviews", keyword)


    response = get_NEJM(keyword)
    thirdValueArr1 = get_Amount(response, NEJMParser)

    response = get_JAMA(keyword)
    thirdValueArr2 = get_Amount(response, JAMAParser)

    thirdValueArr3 = get_ScienceDirect_amount("The Lancet", keyword)
    
    mergedSecondValueArr = merge_three_year_count_arrs(secondValueArr1, secondValueArr2, secondValueArr3)
    mergedThirdValueArr = merge_three_year_count_arrs(thirdValueArr1, thirdValueArr2, thirdValueArr3)

    return [mergedSecondValueArr, mergedThirdValueArr]
    









