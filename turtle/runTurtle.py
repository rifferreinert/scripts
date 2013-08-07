import datetime
import turtle

def main(url, startDate, endDate, db):
    sd = datetime.datetime.strptime(startDate, '%Y%m%d')    
    ed = datetime.datetime.strptime(endDate, '%Y%m%d')    
    oneDay = datetime.timedelta(1) 
    urls = []
    dates = []
    while sd <= ed:
        dates.append(sd)
        urls.append(url + '?date=' + sd.strftime('%Y%m%d') + '&confId=50')
        sd += oneDay
    for i, u in enumerate(urls):
        print('scraping {}'.format(u))
        page = turtle.gamePage(u, dates[i])
        page.evaluate_page(db)

        
        
