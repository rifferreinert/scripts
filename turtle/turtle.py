import datetime
from datetime import time
from datetime import date
from datetime import timedelta
import re
import sys
import scraper

def get_game_pages(urlList, baseUrl):
    """quickly makes game pages from a list or urls"""
    exp = re.compile(r'date=(\d+)')
    urlList = list(urlList)
    return map(lambda x : gamePage(x[0], exp.search(x[1]).group(1), baseUrl), zip(scraper.soup_links(urlList, 40, 0), urlList)) 

def get_play_by_plays(triples):  
    """quickly makes an itterator of playbyplays from a list of (url, hometeam, awayteam)"""
    triples = list(triples)
    return map(lambda x : playByPlays(x[0], x[1], x[2]), zip(
        scraper.soup_links(map(lambda x : x[0], triples) , 50, 0), 
        map(lambda x : x[1], triples), 
        map(lambda x : x[2], triples)))

def insert_into_database(shot, game, db):
    cursor = db.cursor()
    cursor.execute("""INSERT INTO game_table (home_team, away_team, home_score, away_score, playoff_status, game_date, home_wins, away_wins, home_losses, away_losses) 
                   VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (str(game.homeTeam), str(game.awayTeam), str(game.homeScore), str(game.awayScore), str(game.playoffStatus), 
                   game.date, str(game.homeWins), str(game.awayWins), str(game.homeLosses), str(game.awayLosses)))
    gameID = cursor.lastrowid
    cursor.execute("""INSERT INTO shot_table (game_id, success, time_remaining, player_name, shot_number, period, home_previous_score, away_previous_score, team) 
                   VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                  (gameID, shot.success, shot.time, shot.playerName, shot.shotNumber, shot.period, shot.homeLastScore,
                  shot.awayLastScore, shot.side))
    db.commit()

class shot:
    def __init__(self, time, success, shotNumber, playerName, teamName, homeLastScore, awayLastScore , period, side):
        self.time = time
        self.success = success
        self.shotNumber = shotNumber
        self.playerName = playerName
        self.teamName = teamName
        self.homeLastScore = homeLastScore
        self.awayLastScore = awayLastScore
        self.period = period
        self.side = side
   
class game:
    def __init__(self, url, date, homeTeam, homeScore, awayTeam, awayScore, playoffStatus, homeWins, homeLosses, awayWins, awayLosses):
        self.url = url
        self.date = date
        self.homeTeam = homeTeam
        self.homeScore = homeScore
        self.awayTeam = awayTeam
        self.awayScore = awayScore
        self.playoffStatus = playoffStatus
        self.homeWins = homeWins
        self.homeLosses = homeLosses
        self.awayWins = awayWins
        self.awayLosses = awayLosses

    def evaluate_game(self, db):
        print('evaluate_game')
        if self.pbp.shots:
            for s in self.pbp.shots:
                insert_into_database(s, self, db)

class playByPlays:
    def __init__(self, soup, homeTeam, awayTeam):
        print('making a play by play')
        self.homeTeam = homeTeam
        self.awayTeam = awayTeam
       # self.shots = self.get_shots_from_box(self.get_shot_box_from_soup(get_soup_from_link(url)))
        self.soup = soup
        self.shots = self.get_shot_box_from_soup(self.soup)
    
    def get_shot_box_from_soup(self, soup):
        try:
            shotBox =  soup.find(class_ = 'mod-container').find(class_ = 'mod-content')
            return shotBox
        except:
            return None 

    def get_shots_from_box(self, box):
        if not box:
            return None
        parsedShots = []
        shots = box.find_all(class_ = re.compile(r'(odd)|(even)'))
        action = ''
        time = ''
        previousTime = ''
        nextScore = ''
        numThrowsInARow = 0
        lastPlayer = ''
        player = ''
        awayPreviousScore = 0
        homePreviousScore = 0
        success = 0
        half = 1
        lastThrowTime = ''
        team = ''
        for ushot in shots:
            ushotAttrs = list(attr.string for attr in ushot.find_all('td'))
            if len(ushotAttrs) != 4:
                continue
            time = datetime.datetime.strptime(ushotAttrs[0], '%M:%S')
            #if we went back in time that means we are in the next half of the game

            if previousTime == '':
                previousTime = time
            if (previousTime - time).days < 0:
                previousTime = '' 
                half += 1
                numThrowsInARow = 0
            
            if ushotAttrs[1] == '\xa0':
                action = ushotAttrs[3]
                team = self.homeTeam
                side= 'home'
            else:
                action = ushotAttrs[1]
                team = self.awayTeam
                side= 'away'
            if not action:
                continue
            #check to make sure it's a free throw
            if re.compile(r'(?i)Free\s+Throw').search(action):
                #find player name
                #name should come just before 'made' or 'missed'
                nameMatch = re.compile(r'(?i)(.+\S)\s+(made|missed)').search(action)
                if nameMatch:
                    #remove any extra spaces
                    player = re.sub('\s+', ' ', nameMatch.group(1))
                else:
                    #for some the first re didn't match. Assume the player's name is the 
                    #first two words
                    nameMatch = re.compile(r'(?i)(/w+)\s+(/w+)').search(action)
                    if nameMatch:
                        player = nameMatch.group(1) + nameMatch.group(2)
                    else:
                        player = 'no player name found'
                #was the throw a success?
                if re.compile(r'(?i)made').search(action):
                    success = 1
                elif re.compile(r'(?i)missed').search(action):
                    success = 0
                else:
                    success = 'NULL'
                #run logic to count consecutive shots
                if lastPlayer == player and time == lastThrowTime:
                    numThrowsInARow += 1
                else:
                    numThrowsInARow = 0
                lastThrowTime = time
                lastPlayer = player
                #make the shot
                parsedShots.append(shot(time,success, numThrowsInARow + 1, player, team, awayPreviousScore, homePreviousScore, half, side))
            awayPreviousScore = int(re.compile(r'(\d+)-').search(ushotAttrs[2]).group(1))
            homePreviousScore = int(re.compile(r'.*-(\d+)').search(ushotAttrs[2]).group(1))
            previousTime = time 
        return parsedShots


class gamePage:
    def __init__(self, soup, date, baseUrl):
        self.date = date 
        self.baseUrl = baseUrl
        self.soup = soup
 #      gameSelection = soup.find(attrs = {'name' : 'Conference List'}).find(lambda x : x.has_attr('selected')).string
 #      #make sure we are looking at the right page
 #      if gameSelection != 'NCAA Tourney' and gameSelection != 'All':
 #          for child in soup.find(attrs = {'name' : 'Conference List'}).children:
 #              if child.string == 'NCAA Tourney' or child.string == 'All':
 #                  url = re.sub(r'(.*)\?.*' ,r'\1' + child['value'], url) 
 #                  soup = get_soup_from_link(url)
 #                  break
       
    def evaluate_page(self, db):
        self.boxes = self.get_game_boxes_from_soup(self.soup)
        self.games = []
        for box in self.boxes:
            ht = self.get_home_team_from_box(box)
            at = self.get_away_team_from_box(box)
            hs = self.get_home_score_from_box(box)
            ascore = self.get_away_score_from_box(box)
            ps = self.get_playoff_status_from_box(box)
            homeRecord = self.get_home_record_from_box(box)
            awayRecord = self.get_away_record_from_box(box)
            if homeRecord:
                hw = re.search(r'(\d+)-\d+' ,homeRecord).group(1)
                hl = re.search(r'\d+-(\d+)', homeRecord).group(1)
            else:
                hw = 'NULL'
                hl = 'NULL'
            if awayRecord:
                aw = re.search(r'(\d+)-\d+', awayRecord).group(1)
                al = re.search(r'\d+-(\d+)', awayRecord).group(1) 
            else:
                aw = 'NULL'
                al = 'NULL'
            pageUrl = self.get_play_by_play_link_from_box(box)
            g = game(date = self.date, homeTeam = ht, awayTeam = at, homeScore = hs, awayScore = ascore, playoffStatus = ps,
                homeWins = hw, homeLosses = hl, awayWins = aw, awayLosses = al, url = pageUrl)
            self.games.append(g)
#           try:
#               g.evaluate_game(db)
#           except :
#               print('No Shots For {}'.format(pageUrl))
#               print(sys.exc_info())

        #download playbyplays and add them to the game objects
        for x in get_play_by_plays(map(lambda x : (x.url, x.homeTeam, x.awayTeam), self.games)):
            print(type(x))

        for g, plays in zip(self.games, get_play_by_plays(map(lambda x : (x.url, x.homeTeam, x.awayTeam), self.games))):
            print('in evaluate loop')
            g.pbp = plays
            g.evaluate_game(db)


    def get_game_boxes_from_soup(self, soup):
        return list(filter(lambda x : x.find(href = re.compile('playbyplay')) != None, soup.find_all(class_ = re.compile('gameCount'))))

    def get_play_by_play_link_from_box(self, box):
        return self.baseUrl + box.find(href = re.compile('playbyplay'))['href']

    def get_home_team_from_box(self, box):
        teamLink = box.find_next(class_ = 'team home').find_next(class_ = 'team-capsule').find_next(class_ = 'team-name').find_next(id = re.compile('TeamName'))
        if teamLink.a:
            return teamLink.a.string
        else:
            return teamLink.string

    def get_away_team_from_box(self, box):
        teamLink = box.find_next(class_ = 'team visitor').find_next(class_ = 'team-capsule').find_next(class_ = 'team-name').find_next(id = re.compile('TeamName'))
        if teamLink.a:
            return teamLink.a.string
        else:
            return teamLink.string

    def get_home_score_from_box(self, box):
        return box.find_next(class_ = 'team home').find_next(class_ = 'score').find_next(class_ = 'final').string

    def get_away_score_from_box(self, box):
        return box.find_next(class_ = 'team visitor').find_next(class_ = 'score').find_next(class_ = 'final').string

    def get_home_record_from_box(self, box):
        match =  re.compile(r'\((\d+-\d+),.*').search(box.find_next(class_ = 'team home').find_next(class_ = 'team-capsule').find_next(class_ = 'record').string)
        if match:
            return match.group(1)
        else:
            return False

    def get_away_record_from_box(self, box):
        match = re.compile(r'\((\d+-\d+),.*').search(box.find_next(class_ = 'team visitor').find_next(class_ = 'team-capsule').find_next(class_ = 'record').string)
        if match :
            return match.group(1)
        else:
            return False

    def get_playoff_status_from_box(self, box):
        note = box.find_next(id = re.compile('gameNote')).string
        if note == '\xa0':
            return 'No Note'
        else:
            return note
