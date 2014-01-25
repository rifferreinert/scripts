import datetime
import turtle
import sqlite3
from concurrent.futures import ThreadPoolExecutor

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i+n]

def evaluate_url(url, baseUrl, db):
    print('evaluating ' + url) 
    #urlList = turtle.get_acceptable_pages(url, {'NIT', 'All', 'NCAA Tourney'})
    urlList = [(url, 'All')]
    pages = turtle.get_game_pages(urlList, baseUrl, 'wnba')
    print("evaluate page") 
    for page in pages:
        page.evaluate_page(db)

def main(url, baseUrl, startDate, endDate, dbName):
    open(dbName, 'w').close()
    db = sqlite3.connect(dbName)
    cursor = db.cursor() 
    cursor.execute('CREATE TABLE game_table (game_id INTEGER PRIMARY KEY, home_team TEXT, away_team TEXT, home_score INTEGER, away_score INTEGER, playoff_status TEXT, game_date NUMERIC, home_wins INTEGER, away_wins INTEGER, home_losses INTEGER, away_losses INTEGER, tourney TEXT)')
    cursor.execute('CREATE TABLE shot_table (shot_id INTEGER PRIMARY KEY, game_id INTEGER, success INTEGER, time_remaining NUMERIC, player_name TEXT, shot_number INTEGER, period INTEGER, home_previous_score INTEGER, away_previous_score INTEGER, team TEXT, FOREIGN KEY (game_id) REFERENCES game_table(game_id))')
    db.commit()
    sd = datetime.datetime.strptime(startDate, '%Y%m%d')    
    ed = datetime.datetime.strptime(endDate, '%Y%m%d')    
    oneDay = datetime.timedelta(1) 
    urls = []
    dates = []
    executor = ThreadPoolExecutor(max_workers = 8)
    while sd <= ed:
        u = url + '?date=' + sd.strftime('%Y%m%d')# + '&confId=50'
        sd += oneDay
        print("URL: " + u)
        evaluate_url(u, baseUrl, db)
    print("after")
    executor.shutdown(wait=True)
    db.close()

        
        
