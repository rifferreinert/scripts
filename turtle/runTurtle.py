import datetime
import scrape

def main(url, startDate, endDate):
    sd = datetime.datetime.strptime(startDate, '%Y%m%d')    
    ed = datetime.datetime.strptime(endDate, '%Y%m%d')    
    oneDay = datetime.timedelta(1) 
    urls = []
    while sd <= ed:
        sd += oneDay
        urls.append(url + '?date=' sd.strftime('%Y%m%d') + '&confId=50')
    for u in urls:
        page = gamePage(u)
        
        
