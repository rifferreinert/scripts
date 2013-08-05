import datetime
from datetime import time
from datetime import date
from datetime import timedelta
import re
from bs4 import BeautifulSoup as bs
from urllib.request import urlopen
import mysql.connector

class shot:
    def __init__(self, time, success, shotNumber, playerName, teamName, homeLastScore, awayLastScore , period):
        self.time = time
        self.success = success
        self.shotNumber = shotNumber
        self.playerName = playerName
        self.teamName = teamName
        self.homeLastScore = homeLastScore
        self.awayLastScore = awayLastScore
        self.period = period
    
    def insert_into_table(self, db):
        pass 

class game:
    def __init__(self, url, date, homeTeam, awayTeam, awayScore, playoffStatus, homeWins, homeLosses, awayWins, awayLosses):
        self.url = url
        self.date = date
        self.homeTeam = homeTeam
        self.awayTeam = awayTeam
        self.awayScore = awayScore
        self.playoffStatus = playoffStatus
        self.homeWins = homeWins
        self.homeLosses = homeLosses
        self.awayWins = awayWins
        self.awayLosses = awayLosses
        self.playByPlays = playByPlays(url, homeTeam, awayTeam)

    def insert_into_table(db):
        cursor = db.cursor()
        cursor.execute('INSERT INTO game_table VALUES({}, {}, {}, {}, {}, {}, {}, {}, {})'.format(self.gameID, self.homeTeam, self.awayTeam, self.homeScore,
            self.awayScore, self.playoffStatus, self.date, self.homeWins, self.awayWins, self.homeLosses, self.awayLosses))


def get_soup_from_link(link):
    return bs(urlopen(link))

class playByPlays:
    def __init__(self, url, homeTeam, awayTeam):
        self.box = self.get_shot_box_from_soup(get_soup_from_link(url))
        self.homeTeam = homeTeam
        self.awayTeam = awayTeam
        
    def get_shot_box_from_soup(self, soup):
        return soup.find(class_ = 'mod-container').find(class_ = 'mod-content')

    def get_shots_from_box(self, box):
        parsedShots = []
        shots = box.find_all(class_ = re.compile(r'(odd)|(even)'))
        action = ''
        time = ''
        previousTime = ''
        nextScore = ''
        numThrowsInARow = 0
        lastPlayer = ''
        player = ''
        previousScore = '0-0'
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
                previousTime = datetime.datetime.strptime('20:00', '%M:%S')
                half += 1
                numThrowsInARow = 0
            if ushotAttrs[1] == '\xa0':
                action = ushotAttrs[3]
                team = self.homeTeam
            else:
                action = ushotAttrs[1]
                team = self.awayTeam
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
                    success = 'unknown'
                #run logic to count consecutive shots
                if lastPlayer == player and time == lastThrowTime:
                    numThrowsInARow += 1
                else:
                    numThrowsInARow = 0
                lastThrowTime = time
                lastPlayer = player
                #make the shot
                parsedShots.append(shot(time,success, numThrowsInARow + 1, player, team, awayPreviousScore, homePreviousScore, half))
            awayPreviousScore = re.compile(r'(\d+)-').search(ushotAttrs[2]).group(1)
            homePreviousScore = re.compile(r'.*-(\d+)').search(ushotAttrs[2]).group(1)
        return parsedShots


class gamePage:
    def __init__(self, url, date, db):
        self.date = date
        self.baseUrl = re.compile(r'(.*.\.com).*').search(url).group(1)
        soup = get_soup_from_link(url)
        gameSelection = soup.find(attrs = {'name' : 'Conference List'}).find(lambda x : x.has_attr('selected')).string
        #make sure we are looking at the right page
        if gameSelection != 'NCAA Tourney' and gameSelection != 'All':
            for child in soup.find(attrs = {'name' : 'Conference List'}).children:
                if child.string == 'NCAA Tourney' or child.string == 'All':
                    url = re.sub(r'(.*)\?.*' ,r'\1' + child['value'], url) 
                    soup = get_soup_from_link(url)
                    break
        self.boxes = self.get_game_boxes_from_soup(soup)
       
    def evaluate_page(self):
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
                hw = None
                hl = None
            if awayRecord:
                aw = re.search(r'(\d+)-\d+', awayRecord).group(1)
                al = re.search(r'\d+-(\d+)', awayRecord).group(1) 
            else:
                aw = None
                al = None
            pageUrl = self.get_play_by_play_link_from_box(box)
            g = game(date = self.date, homeTeam = ht, awayTeam = at, awayScore = ascore, playoffStatus = ps,
                homeWins = hw, homeLosses = hl, awayWins = aw, awayLosses = al, url = pageUrl)
            self.games.append(g)
           # g.insert_into_table(db)

    def get_game_boxes_from_soup(self, soup):
        return list(filter(lambda x : x.find_next(href = re.compile('playbyplay')) != None, soup.find_all(attrs={'class': re.compile('gameCount')})))

    def get_game_boxes_from_url(self, url):
        return get_game_boxes_from_soup(get_soup_from_link(url))


    def get_play_by_play_links(self, url):
        links =  list(map(lambda x : url+ x['href'], get_soup_from_link(url).find_all('a', href = re.compile('playbyplay'))))
        return links


    def get_soups_from_links(self, ls):
        return list(map(get_soup_from_link, ls)) 

    def get_play_by_play_link_from_box(self, box):
        return self.baseUrl + box.find_next(href = re.compile('playbyplay'))['href']

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
