import datetime
import turtle
import sqlite3

def main(url, startDate, endDate, dbName):
    open(dbName, 'w').close()
    db = sqlite3.connect(dbName)
    cursor = db.cursor() 
    cursor.execute('CREATE TABLE game_table (game_id INTEGER PRIMARY KEY, home_team TEXT, away_team TEXT, home_score INTEGER, away_score INTEGER, playoff_status TEXT, game_date NUMERIC, home_wins INTEGER, away_wins INTEGER, home_losses INTEGER, away_losses INTEGER)')
    cursor.execute('CREATE TABLE shot_table (shot_id INTEGER PRIMARY KEY, game_id INTEGER, success INTEGER, time_remaining NUMERIC, player_name TEXT, shot_number INTEGER, period INTEGER, home_previous_score INTEGER, away_previous_score INTEGER, team TEXT, FOREIGN KEY (game_id) REFERENCES game_table(game_id))')
    db.commit()
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
    db.close()

        
        
