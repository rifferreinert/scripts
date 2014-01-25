import datetime
from datetime import time
from datetime import date
from datetime import timedelta
import re
import sys
import scraper

def get_game_pages(urlList, baseUrl, league = None):
    """quickly makes game pages from a list or urls"""
    exp = re.compile(r'date=(\d+)')
    urlList = list(urlList)
    return map(lambda x : gamePage(x[0], exp.search(x[1]).group(1), baseUrl, x[2], league),
               zip(scraper.soup_links(map(lambda y : y[0], urlList), 40, 0), 
               map(lambda y : y[0], urlList), 
               map(lambda y : y[1], urlList))) 

def get_play_by_plays(triples):  
    """quickly makes an itterator of playbyplays from a list of (url, hometeam, awayteam)"""
    triples = list(triples)
    return map(lambda x : playByPlays(x[0], x[1], x[2]), zip(
        scraper.soup_links(map(lambda x : x[0], triples) , 50, 0), 
        map(lambda x : x[1], triples), 
        map(lambda x : x[2], triples)))

def get_acceptable_pages(url, choices):
    soup = scraper.soup_link(url, 0)
    selections = soup.find(attrs = {'name' : 'Conference List'})
    urlList = []
    for child in selections.children:
        if child.string in choices:
            urlList.append((re.sub(r'(.*)\?.*' ,r'\1' + child['value'], url), child.string))
    print("acceptable pages: {}".format(str(urlList)))
    return urlList

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

    def insert_into_database(self, gameID, db):
        cursor = db.cursor()
        cursor.execute("""INSERT INTO shot_table (game_id, success, time_remaining, player_name, shot_number, period, home_previous_score, away_previous_score, team) 
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
              (gameID, self.success, self.time, self.playerName, self.shotNumber, self.period, self.homeLastScore,
              self.awayLastScore, self.side))

   
class game:
    def __init__(self, url, date, homeTeam, homeScore, awayTeam, awayScore, playoffStatus, homeWins, homeLosses, awayWins, awayLosses, tourney):
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
        self.tourney = tourney
    def insert_into_database(self, db):
        cursor = db.cursor()
        cursor.execute("""INSERT INTO game_table (home_team, away_team, home_score, away_score, playoff_status, game_date, home_wins, away_wins, home_losses, away_losses, tourney) 
                       VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (str(self.homeTeam), str(self.awayTeam), str(self.homeScore), str(self.awayScore), str(self.playoffStatus), 
                       self.date, str(self.homeWins), str(self.awayWins), str(self.homeLosses), str(self.awayLosses), str(self.tourney)))
        return cursor.lastrowid

    def evaluate_game(self, db):
        gameID = self.insert_into_database(db)
        if self.pbp.shots and len(self.pbp.shots) > 0:
            for s in self.pbp.shots:
                s.insert_into_database(gameID, db)
                db.commit()
        else:
            db.rollback()
                
class playByPlays:
    def __init__(self, soup, homeTeam, awayTeam):
        self.homeTeam = homeTeam
        self.awayTeam = awayTeam
      #  self.shots = self.get_shots_from_box(self.get_shot_box_from_soup(get_soup_from_link(url)))
        self.soup = soup
        self.shotBox = self.get_shot_box_from_soup(self.soup)
        self.shots = []
        shotsLeft = True
        period = 0
        shot = self.shotBox
        if not shot:
            shotsLeft = False
        while shotsLeft:
            shot = shot.find_next(re.compile(r'(tr)|(thead)'))
            if not shot:
                shotsLeft = False
            else:
                if re.compile(r'thead').search(shot.name):
                    period += 1
                else:
                    shot_class = shot.get('class')
                    if shot_class and re.compile(r'(odd)|(even)').search(shot_class[0]):
                        self.shots.append((shot, period))

        self.shots = self.parse_shots(self.shots)
         
    def get_shot_box_from_soup(self, soup):
        try:
            shotBox = soup.find(class_ = 'mod-container').find(class_ = 'mod-content')
            return shotBox 
        except:
            return None 

    def parse_shots(self, shots):
        if len(shots) == 0:
            return None
        parsedShots = []
        action = ''
        time = ''
        nextScore = ''
        numThrowsInARow = 0
        lastPlayer = ''
        player = ''
        awayPreviousScore = 0
        homePreviousScore = 0
        success = 0
        lastThrowTime = ''
        team = ''
        for ushot in shots:
            period = ushot[1]
            ushot = ushot[0]
            ushotAttrs = list(attr.string for attr in ushot.find_all('td'))
            if len(ushotAttrs) != 4:
                continue
            time = datetime.datetime.strptime(ushotAttrs[0], '%M:%S')
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
                nameMatch = re.compile(r'(?i)(.+\S)\s+(made|missed|makes|misses)').search(action)
                if nameMatch:
                    #remove any extra spaces
                    player = re.sub('\s+', ' ', nameMatch.group(1))
                else:
                    #for some the first re didn't match. Assume the player's name is the 
                    #first two words
                    nameMatch = re.compile(r'(?i)(\w+)\s+(\w+)').search(action)
                    if nameMatch:
                        player = nameMatch.group(1) + nameMatch.group(2)
                    else:
                        player = None
                #was the throw a success?
                if re.compile(r'(?i)(made)|(makes)').search(action):
                    success = 1
                elif re.compile(r'(?i)(missed)|(misses)').search(action):
                    success = 0
                else:
                    success = None
                #run logic to count consecutive shots
                if lastPlayer == player and time == lastThrowTime and period == lastPeriod:
                    numThrowsInARow += 1
                else:
                    numThrowsInARow = 0
                lastThrowTime = time
                lastPlayer = player
                lastPeriod = period
                #make the shot
                parsedShots.append(shot((time - datetime.datetime(1900,1,1)).total_seconds(),success, numThrowsInARow + 1, player, team, homePreviousScore, awayPreviousScore, period, side))
            awayPreviousScore = int(re.compile(r'(\d+)-').search(ushotAttrs[2]).group(1))
            homePreviousScore = int(re.compile(r'.*-(\d+)').search(ushotAttrs[2]).group(1))
        parsedShots.append(shot(1201, 0, 0, '','', homePreviousScore, awayPreviousScore,0,''))
        return parsedShots


class gamePage:
    def __init__(self, soup, date, baseUrl, tourney, league = None):
        self.date = date 
        self.baseUrl = baseUrl
        self.soup = soup
        self.tourney = tourney
        self.league = league
        self.games = []
       
    def evaluate_page(self, db):
        self.boxes = self.get_game_boxes_from_soup(self.soup)
        for box in self.boxes:
            try:
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
                    homeWins = hw, homeLosses = hl, awayWins = aw, awayLosses = al, url = pageUrl, tourney = self.tourney)
                self.games.append(g)
            except Exception as e:
                print('Error reading ' + str(self.date))
                print(e)
                print(sys.exc_info())
        #download playbyplays and add them to the game objects
        for g, plays in zip(self.games, get_play_by_plays(map(lambda x : (x.url, x.homeTeam, x.awayTeam), self.games))):
            g.pbp = plays
            g.evaluate_game(db)


    def get_game_boxes_from_soup(self, soup):
        if self.league == 'nba':
            return list(filter(lambda x : x.find(href = re.compile('playbyplay')) != None, soup.find_all(attrs = {'id' : re.compile('gamebox')})))

        else:
            return list(filter(lambda x : x.find(href = re.compile('playbyplay')) != None, soup.find_all(attrs = {'id' : re.compile('gameHeader')})))

    def get_play_by_play_link_from_box(self, box):
        return self.baseUrl + box.find(href = re.compile('playbyplay'))['href'] + '&period=0'

    def get_home_team_from_box(self, box):
        if self.league == 'wnba':
            navigation = [{'attrs' : {'class' : 'team home'}},
                          {'attrs' : {'class' : 'team-capsule'}},
                          {'attrs' : {'class' : 'team-name'}}]
            team = scraper.navigate(box, navigation)
            return team.find_all('span')[1].string
        else:
            navigation = [{'attrs' : {'class' : 'team home'}},
                          {'attrs' : {'class' : 'team-capsule'}},
                          {'attrs' : {'class' : 'team-name'}},
                          {'attrs' : {'id' : re.compile('TeamName')}}]
            teamLink = scraper.navigate(box, navigation)
            if teamLink.a:
                return teamLink.a.string
            else:
                return teamLink.string

    def get_away_team_from_box(self, box):
        if self.league == 'wnba' :
            navigation = [{'attrs' : {'class' : 'team visitor'}},
                          {'attrs' : {'class' : 'team-capsule'}},
                          {'attrs' : {'class' : 'team-name'}}]
            team = scraper.navigate(box, navigation)
            return team.find_all('span')[1].string
        elif self.league == 'nba':
            navigation = [{'attrs' : {'class' : 'team away'}},
                          {'attrs' : {'class' : 'team-capsule'}},
                          {'attrs' : {'class' : 'team-name'}},
                          {'attrs' : {'id' : re.compile('TeamName')}}]
            teamLink = scraper.navigate(box, navigation)
            if teamLink.a:
                return teamLink.a.string
            else:
                return teamLink.string
        else:
            navigation = [{'attrs' : {'class' : 'team visitor'}},
                          {'attrs' : {'class' : 'team-capsule'}},
                          {'attrs' : {'class' : 'team-name'}},
                          {'attrs' : {'id' : re.compile('TeamName')}}]
            teamLink = scraper.navigate(box, navigation)
            if teamLink.a:
                return teamLink.a.string
            else:
                return teamLink.string

    def get_home_score_from_box(self, box):
        navigation = [{'attrs' : {'class' : 'team home'}},
                      {'attrs' : {'class' : 'score'}},
                      {'attrs' : {'class' : re.compile('final')}}]
        return scraper.navigate(box, navigation).string

    def get_away_score_from_box(self, box):
        if self.league == 'nba':
            navigation = [{'attrs' : {'class' : 'team away'}},
                          {'attrs' : {'class' : 'score'}},
                          {'attrs' : {'class' : re.compile('final')}}]
        else:
            navigation = [{'attrs' : {'class' : 'team visitor'}},
                          {'attrs' : {'class' : 'score'}},
                          {'attrs' : {'class' : re.compile('final')}}]
        return scraper.navigate(box, navigation).string

    def get_home_record_from_box(self, box):
        navigation = [{'attrs' : {'class' : 'team home'}},
                      {'attrs' : {'class' : 'team-capsule'}},
                      {'attrs' : {'class' : 'record'}}]
        match = re.compile(r'\((\d+-\d+),.*').search(scraper.navigate(box, navigation).string)
        if match:
            return match.group(1)
        else:
            return False

    def get_away_record_from_box(self, box):
        if self.league == 'nba':
            navigation = [{'attrs' : {'class' : 'team away'}},
                          {'attrs' : {'class' : 'team-capsule'}},
                          {'attrs' : {'class' : 'record'}}]
        else:
            navigation = [{'attrs' : {'class' : 'team visitor'}},
                          {'attrs' : {'class' : 'team-capsule'}},
                          {'attrs' : {'class' : 'record'}}]
        match = re.compile(r'\((\d+-\d+),.*').search(scraper.navigate(box, navigation).string)
        if match :
            return match.group(1)
        else:
            return False

    def get_playoff_status_from_box(self, box):
        note = box.find(id = re.compile('gameNote')).string
        if note == '\xa0':
            return 'No Note'
        else:
            return note
