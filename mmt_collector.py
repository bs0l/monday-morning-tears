#v2.2
#24sep26
#tied-owner superlatives (win/loss streaks, weekly
#high/low scorers, all-time + season-level) and 0-0 placeholder-score guard
#in the box_scores matchup loop
#restores keepers
#!/usr/bin/env python3
"""
ESPN Fantasy Football Data Collector using espn-api library
This properly handles all years including 2013-2018
"""

from espn_api.football import League
import json
from datetime import datetime
from collections import defaultdict, Counter
import os
import argparse
import requests
from dotenv import load_dotenv

load_dotenv("/home/pi/fantasystats/.env")

# Configuration
LEAGUE_ID = 1483079
OUTPUT_DIR = "output"

# Hardcoded keeper identities (2017-2021), manual point overrides for keepers
# ESPN has scrubbed from historical API data, and season-stats-page notes for
# those same keepers. Contains real owner/player names, so this lives in a
# separate gitignored file (not committed to GitHub) rather than inline here.
# See mmt_keepers.py for the format -- that file must be SCP'd to the Pi
# manually after editing, the same way this collector script used to be
# before it started being deployed via git.
try:
    from mmt_keepers import KEEPER_DATA, KEEPER_POINT_OVERRIDES, KEEPER_NOTES
except ImportError as e:
    raise ImportError(
        "mmt_keepers.py not found. This file holds KEEPER_DATA, "
        "KEEPER_POINT_OVERRIDES and KEEPER_NOTES and is intentionally "
        "gitignored (it contains real owner names), so it must exist "
        "alongside mmt_collector.py on whatever machine is running it but "
        "is never pulled in by git. Copy it over (e.g. via scp) before running."
    ) from e

# Authentication (required for private leagues and historical data)
SWID = os.environ["MMT_SWID"]
ESPN_S2 = os.environ["MMT_S2"]

# Year range
START_YEAR = 2013
_now = datetime.now()
END_YEAR = _now.year if _now.month >= 9 else _now.year - 1

class ESPNDataCollectorV2:
    def __init__(self, league_id, start_year, end_year, swid=None, espn_s2=None):
        self.league_id = league_id
        self.start_year = start_year
        self.end_year = end_year
        self.swid = swid
        self.espn_s2 = espn_s2
        self.all_seasons = []
    
    def fetch_all_seasons(self):
        """Fetch data for all seasons using espn-api library"""
        print(f"\n{'='*80}")
        print(" Fetching Season Data")
        print(f"{'='*80}")
        
        for year in range(self.start_year, self.end_year + 1):
            try:
                print(f"\n  Fetching {year} season...")
                
                league = League(
                    league_id=self.league_id,
                    year=year,
                    espn_s2=self.espn_s2,
                    swid=self.swid
                )
                
                print(f"    ✓ League: {league.settings.name}")
                print(f"    ✓ Teams: {len(league.teams)}")
                print(f"    ✓ Weeks: {league.current_week if hasattr(league, 'current_week') else 'N/A'}")
                
                self.all_seasons.append({
                    'year': year,
                    'league': league
                })
                
            except Exception as e:
                print(f"    ✗ Error fetching {year}: {e}")
                continue
        
        print(f"\n  ✓ Successfully fetched {len(self.all_seasons)} seasons")
        return len(self.all_seasons) > 0
    
    def get_most_recent_team_names(self):
        """Get most recent team names and track ALL teams ever in league"""
        team_history = {}
        
        print(f"\n{'='*80}")
        print(" Tracking Team Names & History")
        print(f"{'='*80}")
        
        for season_data in self.all_seasons:
            year = season_data['year']
            league = season_data['league']
            
            for team in league.teams:
                team_id = team.team_id
                
                if team_id not in team_history:
                    team_history[team_id] = {
                        'names': [],
                        'firstYear': year,
                        'lastYear': year,
                        'seasons': []
                    }
                
                team_history[team_id]['names'].append({
                    'year': year,
                    'name': team.team_name,
                    'abbrev': team.team_abbrev,
                    'owner': team.owner if hasattr(team, 'owner') else None
                })
                team_history[team_id]['lastYear'] = max(team_history[team_id]['lastYear'], year)
                team_history[team_id]['firstYear'] = min(team_history[team_id]['firstYear'], year)
                team_history[team_id]['seasons'].append(year)
        
        team_names = {}
        for team_id, history in team_history.items():
            most_recent = max(history['names'], key=lambda x: x['year'])
            
            team_names[team_id] = {
                'name': most_recent['name'],
                'abbrev': most_recent['abbrev'],
                'owner': most_recent['owner'],
                'firstYear': history['firstYear'],
                'lastYear': history['lastYear'],
                'isActive': history['lastYear'] == self.end_year,
                'totalSeasons': len(set(history['seasons']))
            }
            
            status = 'Active' if team_names[team_id]['isActive'] else 'Inactive'
            print(f"    Team {team_id}: {most_recent['name']} ({history['firstYear']}-{history['lastYear']}) - {status}")
        
        return team_names

    def get_owner_name_from_team(self, team, members):
        """Extract owner display name from team object"""
        if not hasattr(team, 'owners') or not team.owners:
            return None
        
        owner_data = team.owners[0]
        
        if isinstance(owner_data, dict):
            if 'firstName' in owner_data and 'lastName' in owner_data:
                first = owner_data.get('firstName', '').strip()
                last = owner_data.get('lastName', '').strip()
                if first or last:
                    return f"{first} {last}".strip()
            
            if 'displayName' in owner_data:
                return owner_data['displayName']
            
            owner_id = owner_data.get('id') or owner_data.get('ownerId')
            if owner_id and owner_id in members:
                member = members[owner_id]
                if hasattr(member, 'firstName') and hasattr(member, 'lastName'):
                    first = getattr(member, 'firstName', '').strip()
                    last = getattr(member, 'lastName', '').strip()
                    if first or last:
                        return f"{first} {last}".strip()
                if hasattr(member, 'display_name'):
                    return member.display_name
            
            return owner_id or str(owner_data)
        else:
            owner_id = owner_data
            
            if owner_id in members:
                member = members[owner_id]
                if hasattr(member, 'firstName') and hasattr(member, 'lastName'):
                    first = getattr(member, 'firstName', '').strip()
                    last = getattr(member, 'lastName', '').strip()
                    if first or last:
                        return f"{first} {last}".strip()
                if hasattr(member, 'display_name'):
                    return member.display_name
            
            return str(owner_id)
            
    def process_all_matchups(self, team_names):
        """Process all matchups from all seasons"""
        print(f"\n{'='*80}")
        print(" Processing Matchups")
        print(f"{'='*80}")
        
        all_matchups = []
        
        for season_data in self.all_seasons:
            year = season_data['year']
            league = season_data['league']
            
            print(f"  Processing {year}...")
            week_count = 0
            
            members = {}
            if hasattr(league, 'members') and league.members:
                try:
                    if hasattr(league.members, 'items'):
                        members = league.members
                    else:
                        members = {m.id: m for m in league.members}
                except (AttributeError, TypeError):
                    members = {}
            
            if year < 2019:
                processed_matchups = set()
                
                for team in league.teams:
                    team_owner = self.get_owner_name_from_team(team, members)
                    
                    for week_idx in range(len(team.schedule)):
                        opponent = team.schedule[week_idx]
                        opponent_owner = self.get_owner_name_from_team(opponent, members)
                        week = week_idx + 1
                        
                        matchup_key = f"{year}_{week}_{min(team.team_id, opponent.team_id)}_{max(team.team_id, opponent.team_id)}"
                        
                        if matchup_key in processed_matchups:
                            continue
                        
                        processed_matchups.add(matchup_key)
                        
                        is_home = team.team_id < opponent.team_id
                        
                        if is_home:
                            home_team = team
                            away_team = opponent
                            home_score = team.scores[week_idx]
                            away_score = opponent.scores[week_idx]
                            home_owner = team_owner
                            away_owner = opponent_owner
                        else:
                            home_team = opponent
                            away_team = team
                            home_score = opponent.scores[week_idx]
                            away_score = team.scores[week_idx]
                            home_owner = opponent_owner
                            away_owner = team_owner
                        
                        if home_score > away_score:
                            winner = 'HOME'
                        elif away_score > home_score:
                            winner = 'AWAY'
                        else:
                            winner = 'TIE'
                        
                        is_playoff = False
                        if hasattr(league.settings, 'reg_season_count'):
                            is_playoff = week > league.settings.reg_season_count
                        else:
                            is_playoff = week > 13
                        
                        clean_matchup = {
                            'id': matchup_key,
                            'year': year,
                            'week': week,
                            'matchupPeriodId': week,
                            'isPlayoff': is_playoff,
                            'playoffType': 'WINNERS_BRACKET' if is_playoff else 'NONE',
                            'home': {
                                'teamId': home_team.team_id,
                                'teamName': home_team.team_name,
                                'teamAbbrev': home_team.team_abbrev,
                                'owner': home_owner,
                                'score': home_score
                            },
                            'away': {
                                'teamId': away_team.team_id,
                                'teamName': away_team.team_name,
                                'teamAbbrev': away_team.team_abbrev,
                                'owner': away_owner,
                                'score': away_score
                            },
                            'winner': winner
                        }
                        
                        all_matchups.append(clean_matchup)
                        week_count += 1
                
                print(f"    ✓ Loaded {week_count} matchups from {year} (via team schedules)")
            
            else:
                if hasattr(league.settings, 'reg_season_count'):
                    total_weeks = league.settings.reg_season_count + 4
                else:
                    total_weeks = 17
                total_weeks = self._completed_weeks(league, total_weeks)
                
                for week in range(1, total_weeks + 1):
                    try:
                        box_scores = league.box_scores(week)
                        
                        if not box_scores:
                            continue
                        
                        for matchup in box_scores:
                            if not hasattr(matchup, 'home_team') or not hasattr(matchup, 'away_team'):
                                continue
                            
                            if not matchup.home_team or not matchup.away_team:
                                continue
                            
                            home_owner = self.get_owner_name_from_team(matchup.home_team, members)
                            away_owner = self.get_owner_name_from_team(matchup.away_team, members)
                            
                            is_playoff = False
                            if hasattr(league.settings, 'reg_season_count'):
                                is_playoff = week > league.settings.reg_season_count
                            else:
                                is_playoff = week > 14
                            
                            home_score = matchup.home_score
                            away_score = matchup.away_score

                            # Skip matchups that haven't actually been played
                            # yet. league.current_week can advance (e.g. on
                            # ESPN's weekly reset) before any games in that
                            # week have been played, so _completed_weeks()
                            # alone doesn't guarantee real data - a week
                            # with both scores still at 0 is a placeholder,
                            # not a real result. A genuine 0-0 final is not
                            # realistically possible in fantasy scoring.
                            if home_score == 0 and away_score == 0:
                                continue

                            clean_matchup = {
                                'id': f"{year}_{week}_{matchup.home_team.team_id}_{matchup.away_team.team_id}",
                                'year': year,
                                'week': week,
                                'matchupPeriodId': week,
                                'isPlayoff': is_playoff,
                                'playoffType': 'WINNERS_BRACKET' if is_playoff else 'NONE',
                                'home': {
                                    'teamId': matchup.home_team.team_id,
                                    'teamName': matchup.home_team.team_name,
                                    'teamAbbrev': matchup.home_team.team_abbrev,
                                    'owner': home_owner,
                                    'score': home_score
                                },
                                'away': {
                                    'teamId': matchup.away_team.team_id,
                                    'teamName': matchup.away_team.team_name,
                                    'teamAbbrev': matchup.away_team.team_abbrev,
                                    'owner': away_owner,
                                    'score': away_score
                                },
                                'winner': 'HOME' if home_score > away_score else 'AWAY' if away_score > home_score else 'TIE'
                            }
                            
                            all_matchups.append(clean_matchup)
                            week_count += 1
                    
                    except Exception as e:
                        continue
                
                print(f"    ✓ Loaded {week_count} matchups from {year} (via box_scores)")
        
        print(f"\n  ✓ Processed {len(all_matchups)} total matchups")
        return all_matchups

    def get_playoff_teams_by_year(self, all_matchups):
        """Determine which teams made playoffs each year based on actual playoff performance"""
        playoff_teams = defaultdict(set)
        
        print(f"\n  Detecting playoff teams by year...")
        
        for season_data in self.all_seasons:
            year = season_data['year']
            league = season_data['league']
            
            members = {}
            if hasattr(league, 'members') and league.members:
                try:
                    if hasattr(league.members, 'items'):
                        members = league.members
                    else:
                        members = {m.id: m for m in league.members}
                except (AttributeError, TypeError):
                    pass
            
            year_playoff_owners = []
            
            for team in league.teams:
                if hasattr(team, 'final_standing') and team.final_standing is not None:
                    num_playoff_teams = getattr(league.settings, 'playoff_team_count', 4)
                    
                    if team.final_standing <= num_playoff_teams:
                        owner = self.get_owner_name_from_team(team, members)
                        
                        if owner:
                            playoff_teams[year].add(owner)
                            year_playoff_owners.append(f"{owner} (standing: {team.final_standing})")
            
            if year_playoff_owners:
                print(f"    {year}: {len(year_playoff_owners)} playoff teams - {', '.join(year_playoff_owners[:3])}...")
        
        return playoff_teams

    def calculate_team_stats(self, all_matchups, team_names):
        """Calculate comprehensive statistics BY OWNER"""
        print(f"\n{'='*80}")
        print(" Calculating Owner Statistics")
        print(f"{'='*80}")
        
        owner_matchups = defaultdict(list)
        owner_info = {}
        
        for matchup in all_matchups:
            home_owner = matchup['home'].get('owner')
            away_owner = matchup['away'].get('owner')
            
            if not home_owner or not away_owner:
                continue
            
            if home_owner not in owner_info:
                owner_info[home_owner] = {
                    'owner': home_owner,
                    'currentTeamName': matchup['home']['teamName'],
                    'currentTeamAbbrev': matchup['home']['teamAbbrev'],
                    'currentTeamId': matchup['home']['teamId'],
                    'firstYear': matchup['year'],
                    'lastYear': matchup['year'],
                    'teamNames': set(),
                    'logoUrl': None
                }
            
            if away_owner not in owner_info:
                owner_info[away_owner] = {
                    'owner': away_owner,
                    'currentTeamName': matchup['away']['teamName'],
                    'currentTeamAbbrev': matchup['away']['teamAbbrev'],
                    'currentTeamId': matchup['away']['teamId'],
                    'firstYear': matchup['year'],
                    'lastYear': matchup['year'],
                    'teamNames': set()
                }
            
            owner_info[home_owner]['lastYear'] = max(owner_info[home_owner]['lastYear'], matchup['year'])
            owner_info[home_owner]['firstYear'] = min(owner_info[home_owner]['firstYear'], matchup['year'])
            owner_info[home_owner]['teamNames'].add(matchup['home']['teamName'])
            
            if matchup['year'] >= owner_info[home_owner]['lastYear']:
                owner_info[home_owner]['currentTeamName'] = matchup['home']['teamName']
                owner_info[home_owner]['currentTeamAbbrev'] = matchup['home']['teamAbbrev']
                owner_info[home_owner]['currentTeamId'] = matchup['home']['teamId']
            
            owner_info[away_owner]['lastYear'] = max(owner_info[away_owner]['lastYear'], matchup['year'])
            owner_info[away_owner]['firstYear'] = min(owner_info[away_owner]['firstYear'], matchup['year'])
            owner_info[away_owner]['teamNames'].add(matchup['away']['teamName'])
            
            if matchup['year'] >= owner_info[away_owner]['lastYear']:
                owner_info[away_owner]['currentTeamName'] = matchup['away']['teamName']
                owner_info[away_owner]['currentTeamAbbrev'] = matchup['away']['teamAbbrev']
                owner_info[away_owner]['currentTeamId'] = matchup['away']['teamId']
            
            owner_matchups[home_owner].append({
                **matchup,
                'isHome': True,
                'teamScore': matchup['home']['score'],
                'opponentScore': matchup['away']['score'],
                'opponentOwner': away_owner,
                'opponentName': matchup['away']['teamName']
            })
            
            owner_matchups[away_owner].append({
                **matchup,
                'isHome': False,
                'teamScore': matchup['away']['score'],
                'opponentScore': matchup['home']['score'],
                'opponentOwner': home_owner,
                'opponentName': matchup['home']['teamName']
            })
            
        playoff_teams_by_year = self.get_playoff_teams_by_year(all_matchups)
        
        owner_stats = {}
                
        for owner, matches in owner_matchups.items():
            if owner not in owner_info:
                continue
            
            matches.sort(key=lambda m: (m['year'], m['week']))
            
            info = owner_info[owner]
            info['foundedYear'] = info['firstYear']
            info['lastActiveYear'] = info['lastYear']
            info['isActive'] = info['lastYear'] == self.end_year
            info['totalSeasons'] = info['lastYear'] - info['firstYear'] + 1
            info['teamId'] = info['currentTeamId']
            info['teamName'] = info['currentTeamName']
            info['abbrev'] = info['currentTeamAbbrev']
            info['allTeamNames'] = list(info['teamNames'])
            del info['teamNames']
            info['playoffYears'] = list({year for year in playoff_teams_by_year if owner in playoff_teams_by_year[year]})
            
            stats = self.calculate_single_team_stats(owner, matches, info, owner_matchups)
            owner_stats[owner] = stats

            # NOW add the logo fetching code HERE (after owner_stats is populated)
            for owner, stats in owner_stats.items():
                # Get logo from most recent season
                most_recent_year = stats['lastActiveYear']
                season_data = next((s for s in self.all_seasons if s['year'] == most_recent_year), None)
                
                if season_data:
                    league = season_data['league']
                    members = {}
                    if hasattr(league, 'members') and league.members:
                        try:
                            if hasattr(league.members, 'items'):
                                members = league.members
                            else:
                                members = {m.id: m for m in league.members}
                        except (AttributeError, TypeError):
                            pass
                    
                    for team in league.teams:
                        team_owner = self.get_owner_name_from_team(team, members)
                        if team_owner == owner:
                            stats['logoUrl'] = team.logo_url if hasattr(team, 'logo_url') and team.logo_url else None
                            break
        
        print(f"  ✓ Calculated stats for {len(owner_stats)} owners")
        return owner_stats
        
    def calculate_head_to_head_stats(self, all_matchups, owner_stats):
        """Calculate head-to-head records between all owners"""
        print(f"\n{'='*80}")
        print(" Calculating Head-to-Head Records")
        print(f"{'='*80}")
        
        h2h_data = {}
        all_owners = list(owner_stats.keys())
        
        for owner in all_owners:
            h2h_data[owner] = {}
            
            for opponent in all_owners:
                if owner == opponent:
                    continue
                
                matchups = []
                for m in all_matchups:
                    home_owner = m['home'].get('owner')
                    away_owner = m['away'].get('owner')
                    
                    if (home_owner == owner and away_owner == opponent) or \
                       (home_owner == opponent and away_owner == owner):
                        matchups.append(m)
                
                if not matchups:
                    continue
                
                wins = 0
                losses = 0
                ties = 0
                points_for = []
                points_against = []
                win_margins = []
                current_streak = {'type': None, 'length': 0}
                longest_win_streak = 0
                current_win_streak = 0
                
                matchups.sort(key=lambda x: (x['year'], x['week']))
                
                for match in matchups:
                    if match['home']['owner'] == owner:
                        my_score = match['home']['score']
                        opp_score = match['away']['score']
                        i_won = match['winner'] == 'HOME'
                        i_lost = match['winner'] == 'AWAY'
                    else:
                        my_score = match['away']['score']
                        opp_score = match['home']['score']
                        i_won = match['winner'] == 'AWAY'
                        i_lost = match['winner'] == 'HOME'
                    
                    points_for.append(my_score)
                    points_against.append(opp_score)
                    
                    if i_won:
                        wins += 1
                        margin = my_score - opp_score
                        win_margins.append(margin)
                        current_win_streak += 1
                        longest_win_streak = max(longest_win_streak, current_win_streak)
                        
                        if current_streak['type'] == 'WIN':
                            current_streak['length'] += 1
                        else:
                            current_streak = {'type': 'WIN', 'length': 1}
                    elif i_lost:
                        losses += 1
                        current_win_streak = 0
                        
                        if current_streak['type'] == 'LOSS':
                            current_streak['length'] += 1
                        else:
                            current_streak = {'type': 'LOSS', 'length': 1}
                    else:
                        ties += 1
                        current_win_streak = 0
                        current_streak = {'type': None, 'length': 0}
                
                h2h_record = {
                    'opponent': opponent,
                    'opponentName': owner_stats[opponent]['teamName'],
                    'wins': wins,
                    'losses': losses,
                    'ties': ties,
                    'winPercentage': wins / (wins + losses) if (wins + losses) > 0 else 0,
                    'totalGames': len(matchups),
                    'pointsFor': sum(points_for),
                    'pointsAgainst': sum(points_against),
                    'avgPointsFor': sum(points_for) / len(points_for) if points_for else 0,
                    'avgPointsAgainst': sum(points_against) / len(points_against) if points_against else 0,
                    'highestScore': max(points_for) if points_for else 0,
                    'lowestScore': min(points_for) if points_for else 0,
                    'biggestWin': max(win_margins) if win_margins else 0,
                    'closestWin': min(win_margins) if win_margins else 0,
                    'longestWinStreak': longest_win_streak,
                    'currentStreak': current_streak,
                    'matchups': matchups
                }
                
                h2h_data[owner][opponent] = h2h_record
        
        print(f"  ✓ Calculated head-to-head for {len(all_owners)} owners")
        return h2h_data

    def calculate_single_team_stats(self, owner, matches, info, all_owner_data):
        """Calculate all stats for a single team"""
        stats = {
            **info,
            'seasonsPlayed': len(set(m['year'] for m in matches)),
            'totalGames': len(matches)
        }
        
        playoff_years = set(info.get('playoffYears', []))

        regular_season = [m for m in matches if not m['isPlayoff'] or m['year'] not in playoff_years]
        playoffs = [m for m in matches if m['isPlayoff'] and m['year'] in playoff_years]

        stats['regularSeason'] = self.calculate_record(regular_season)
        stats['playoffs'] = self.calculate_record(playoffs)
        stats['overall'] = self.calculate_record(matches)
        stats['playoffAppearances'] = len(playoff_years)
        
        # Calculate championships
        stats['championships'] = 0
        stats['championshipAppearances'] = 0
        championship_years = []

        for year in playoff_years:
            season_data = next((s for s in self.all_seasons if s['year'] == year), None)
            if season_data:
                league = season_data['league']
                members = {}
                if hasattr(league, 'members') and league.members:
                    try:
                        if hasattr(league.members, 'items'):
                            members = league.members
                        else:
                            members = {m.id: m for m in league.members}
                    except (AttributeError, TypeError):
                        pass
                
                for team in league.teams:
                    team_owner = self.get_owner_name_from_team(team, members)
                    if team_owner == owner:
                        if hasattr(team, 'final_standing') and team.final_standing is not None:
                            if team.final_standing == 1:
                                stats['championships'] += 1
                                stats['championshipAppearances'] += 1
                                championship_years.append(year)
                            elif team.final_standing == 2:
                                stats['championshipAppearances'] += 1
                        break

        stats['championshipYears'] = championship_years
        
        # Track acquisitions/moves and trades per season
        acquisitions_by_season = {}
        total_trades = None

        for year in set(m['year'] for m in matches):
            season_data = next((s for s in self.all_seasons if s['year'] == year), None)
            if season_data:
                league = season_data['league']
                members = {}
                if hasattr(league, 'members') and league.members:
                    try:
                        if hasattr(league.members, 'items'):
                            members = league.members
                        else:
                            members = {m.id: m for m in league.members}
                    except (AttributeError, TypeError):
                        pass
                
                for team in league.teams:
                    team_owner = self.get_owner_name_from_team(team, members)
                    if team_owner == owner:
                        # Check for acquisitions attribute
                        if hasattr(team, 'acquisitions'):
                            acquisitions_by_season[year] = team.acquisitions
                        elif hasattr(team, 'moves'):
                            acquisitions_by_season[year] = team.moves
                        elif hasattr(team, 'transactions'):
                            acquisitions_by_season[year] = len(team.transactions) if isinstance(team.transactions, list) else team.transactions
                        
                        # Check for trades (only reliable 2019+)
                        if year >= 2019 and hasattr(team, 'trades') and isinstance(team.trades, int):
                            total_trades = (total_trades or 0) + team.trades
                        
                        break

        if acquisitions_by_season:
            most_moves_year = max(acquisitions_by_season.items(), key=lambda x: x[1])
            stats['mostMovesSeason'] = most_moves_year[1]
            stats['mostMovesSeasonYear'] = most_moves_year[0]
        else:
            stats['mostMovesSeason'] = None
            stats['mostMovesSeasonYear'] = None
        
        all_scores = [m['teamScore'] for m in matches]
        stats['totalPointsFor'] = sum(all_scores)
        stats['totalPointsAgainst'] = sum(m['opponentScore'] for m in matches)
        stats['avgPointsFor'] = stats['totalPointsFor'] / len(matches) if matches else 0
        stats['avgPointsAgainst'] = stats['totalPointsAgainst'] / len(matches) if matches else 0
        stats['highestScore'] = max(all_scores) if all_scores else 0
        stats['lowestScore'] = min(all_scores) if all_scores else 0
        stats['totalTrades'] = total_trades
        
        wins = [m for m in matches if self.is_winner(m)]
        losses = [m for m in matches if self.is_loser(m)]
        
        if wins:
            win_margins = [m['teamScore'] - m['opponentScore'] for m in wins]
            stats['biggestWin'] = max(win_margins)
            stats['closestWin'] = min(win_margins)
        else:
            stats['biggestWin'] = 0
            stats['closestWin'] = 0
        
        if losses:
            loss_margins = [m['opponentScore'] - m['teamScore'] for m in losses]
            stats['biggestLoss'] = max(loss_margins)
            stats['closestLoss'] = min(loss_margins)
        else:
            stats['biggestLoss'] = 0
            stats['closestLoss'] = 0
        
        streaks = self.calculate_streaks(matches)
        stats['longestWinStreak'] = streaks['longestWin']
        stats['longestLossStreak'] = streaks['longestLoss']
        stats['currentStreak'] = streaks['current']
        stats['yearlyRecords'] = self.calculate_yearly_records(matches)
        
        # Calculate best and worst opponents (only active owners with 3+ games)
        opponent_records = defaultdict(lambda: {'wins': 0, 'losses': 0, 'games': 0})

        for match in matches:
            opp = match['opponentOwner']
            opponent_records[opp]['games'] += 1
            
            if self.is_winner(match):
                opponent_records[opp]['wins'] += 1
            elif self.is_loser(match):
                opponent_records[opp]['losses'] += 1

        qualified_opponents = {}
        for opp, rec in opponent_records.items():
            if rec['games'] >= 3 and opp in all_owner_data:
                opp_matches = all_owner_data.get(opp, [])
                is_active = any(m['year'] == self.end_year for m in opp_matches)
                if is_active:
                    qualified_opponents[opp] = rec

        if qualified_opponents:
            best_opp = max(qualified_opponents.items(), 
                           key=lambda x: x[1]['wins'] / x[1]['games'] if x[1]['games'] > 0 else 0)
            stats['bestOpponent'] = best_opp[0]
            stats['bestOpponentRecord'] = f"{best_opp[1]['wins']}-{best_opp[1]['losses']}"
            stats['bestOpponentWinPct'] = best_opp[1]['wins'] / best_opp[1]['games'] if best_opp[1]['games'] > 0 else 0
            
            worst_opp = min(qualified_opponents.items(), 
                            key=lambda x: x[1]['wins'] / x[1]['games'] if x[1]['games'] > 0 else 0)
            stats['worstOpponent'] = worst_opp[0]
            stats['worstOpponentRecord'] = f"{worst_opp[1]['wins']}-{worst_opp[1]['losses']}"
            stats['worstOpponentWinPct'] = worst_opp[1]['wins'] / worst_opp[1]['games'] if worst_opp[1]['games'] > 0 else 0
        else:
            stats['bestOpponent'] = None
            stats['worstOpponent'] = None
        
        # Calculate best/worst seasons
        complete_seasons = {}
        for year, record in stats['yearlyRecords'].items():
            total_games = record['regularSeasonWins'] + record['regularSeasonLosses']
            if year < self.end_year or total_games >= 13:
                if total_games > 0:
                    reg_win_pct = record['regularSeasonWins'] / total_games
                    complete_seasons[year] = {
                        'winPercentage': reg_win_pct,
                        'wins': record['regularSeasonWins'],
                        'losses': record['regularSeasonLosses']
                    }

        if complete_seasons:
            best_season = max(complete_seasons.items(), key=lambda x: (x[1]['winPercentage'], x[1]['wins']))
            worst_season = min(complete_seasons.items(), key=lambda x: (x[1]['winPercentage'], -x[1]['wins']))
            most_wins = max(complete_seasons.items(), key=lambda x: x[1]['wins'])
            most_losses = max(complete_seasons.items(), key=lambda x: x[1]['losses'])
            
            stats['bestSeasonWinPct'] = best_season[1]['winPercentage']
            stats['bestSeasonYear'] = best_season[0]
            stats['bestSeasonWins'] = best_season[1]['wins']
            stats['bestSeasonLosses'] = best_season[1]['losses']
            
            stats['worstSeasonWinPct'] = worst_season[1]['winPercentage']
            stats['worstSeasonYear'] = worst_season[0]
            stats['worstSeasonWins'] = worst_season[1]['wins']
            stats['worstSeasonLosses'] = worst_season[1]['losses']
            
            stats['mostWinsSeason'] = most_wins[1]['wins']
            stats['mostWinsSeasonYear'] = most_wins[0]
            stats['mostLossesSeason'] = most_losses[1]['losses']
            stats['mostLossesSeasonYear'] = most_losses[0]
        else:
            stats['bestSeasonWinPct'] = 0
            stats['bestSeasonLosses'] = 0
            stats['bestSeasonWins'] = 0
            stats['worstSeasonWinPct'] = 0
            stats['worstSeasonWins'] = 0
            stats['worstSeasonLosses'] = 0
            stats['mostWinsSeason'] = 0
            stats['mostLossesSeason'] = 0
        
        return stats
    
    def calculate_record(self, matches):
        """Calculate W-L-T record"""
        wins = sum(1 for m in matches if self.is_winner(m))
        losses = sum(1 for m in matches if self.is_loser(m))
        ties = sum(1 for m in matches if m['winner'] == 'TIE')
        
        total = len(matches)
        win_pct = wins / total if total > 0 else 0
        
        return {
            'wins': wins,
            'losses': losses,
            'ties': ties,
            'winPercentage': round(win_pct, 3)
        }
    
    def is_winner(self, match):
        """Check if team won"""
        if match['winner'] == 'TIE' or match['winner'] == 'UNDECIDED':
            return False
        
        if match['isHome']:
            return match['winner'] == 'HOME'
        else:
            return match['winner'] == 'AWAY'
    
    def is_loser(self, match):
        """Check if team lost"""
        if match['winner'] == 'TIE' or match['winner'] == 'UNDECIDED':
            return False
        
        if match['isHome']:
            return match['winner'] == 'AWAY'
        else:
            return match['winner'] == 'HOME'
    
    def calculate_streaks(self, matches):
        """Calculate streaks"""
        if not matches:
            return {'longestWin': 0, 'longestLoss': 0, 'current': {'type': None, 'length': 0}}
        
        longest_win = 0
        longest_loss = 0
        current_streak = 0
        current_type = None
        
        for match in matches:
            if match['winner'] == 'TIE':
                continue
            
            is_win = self.is_winner(match)
            
            if is_win:
                if current_type == 'WIN':
                    current_streak += 1
                else:
                    current_type = 'WIN'
                    current_streak = 1
                longest_win = max(longest_win, current_streak)
            else:
                if current_type == 'LOSS':
                    current_streak += 1
                else:
                    current_type = 'LOSS'
                    current_streak = 1
                longest_loss = max(longest_loss, current_streak)
        
        return {
            'longestWin': longest_win,
            'longestLoss': longest_loss,
            'current': {'type': current_type, 'length': current_streak}
        }
    
    def calculate_yearly_records(self, matches):
        """Calculate yearly records"""
        yearly = defaultdict(list)
        
        for match in matches:
            yearly[match['year']].append(match)
        
        records = {}
        for year, year_matches in yearly.items():
            playoff_games = [m for m in year_matches if m['isPlayoff']]
            regular_games = [m for m in year_matches if not m['isPlayoff']]
            
            record = self.calculate_record(year_matches)
            
            scores = [m['teamScore'] for m in year_matches]
            record['pointsFor'] = sum(scores)
            record['pointsAgainst'] = sum(m['opponentScore'] for m in year_matches)
            record['avgPointsFor'] = record['pointsFor'] / len(year_matches)
            record['madePlayoffs'] = len(playoff_games) > 0
            
            if regular_games:
                reg_record = self.calculate_record(regular_games)
                record['regularSeasonWins'] = reg_record['wins']
                record['regularSeasonLosses'] = reg_record['losses']
            else:
                record['regularSeasonWins'] = 0
                record['regularSeasonLosses'] = 0
            
            records[year] = record
        
        return records
    
    def calculate_superlatives(self, all_matchups):
        """Calculate superlatives"""
        print(f"\n{'='*80}")
        print(" Calculating Superlatives")
        print(f"{'='*80}")
        
        regular_season = [m for m in all_matchups if not m['isPlayoff']]
        
        all_time_streaks = self.calculate_all_time_streaks(all_matchups)
        regular_season_streaks = self.calculate_all_time_streaks(regular_season)
        all_time_weekly = self.calculate_weekly_performance(all_matchups)
        regular_season_weekly = self.calculate_weekly_performance(regular_season)
        
        superlatives = {
            'allTime': {
                **self.calculate_single_superlatives(all_matchups, "All-Time"),
                **all_time_streaks,
                **all_time_weekly
            },
            'regularSeason': {
                **self.calculate_single_superlatives(regular_season, "Regular Season"),
                **regular_season_streaks,
                **regular_season_weekly,
                **self.calculate_seasonal_stats(regular_season)
            }
        }
        
        return superlatives
    
    def calculate_single_superlatives(self, matchups, label):
        """Calculate superlatives for a set of matchups"""
        if not matchups:
            return {}
        
        print(f"  Calculating {label} superlatives...")
        
        # Detect 2-week playoff matchups by finding duplicate matchups in consecutive weeks
        two_week_playoff_weeks = set()
        
        for m in matchups:
            if m['isPlayoff']:
                # Look for the same matchup in the next week (2-week playoff)
                for m2 in matchups:
                    if (m2['isPlayoff'] and 
                        m2['year'] == m['year'] and 
                        m2['week'] == m['week'] + 1 and
                        ((m2['home']['teamId'] == m['home']['teamId'] and m2['away']['teamId'] == m['away']['teamId']) or
                         (m2['home']['teamId'] == m['away']['teamId'] and m2['away']['teamId'] == m['home']['teamId']))):
                        # Found a 2-week playoff - skip the second week
                        two_week_playoff_weeks.add((m2['year'], m2['week']))
        
        # Track individual scores - filter out 2-week playoff duplicates
        all_scores = []
        
        for m in matchups:
            # Skip second week of 2-week playoff matchups
            if (m['year'], m['week']) in two_week_playoff_weeks:
                continue
            
            all_scores.append({
                'score': m['home']['score'],
                'team': m['home']['teamName'],
                'teamId': m['home']['teamId'],
                'owner': m['home']['owner'],
                'opponent': m['away']['teamName'],
                'opponentScore': m['away']['score'],
                'year': m['year'],
                'week': m['week'],
                'matchupPeriodId': m['matchupPeriodId']
            })
            all_scores.append({
                'score': m['away']['score'],
                'team': m['away']['teamName'],
                'teamId': m['away']['teamId'],
                'owner': m['away']['owner'],
                'opponent': m['home']['teamName'],
                'opponentScore': m['home']['score'],
                'year': m['year'],
                'week': m['week'],
                'matchupPeriodId': m['matchupPeriodId']
            })
        
        # Rest stays the same...
        
        non_zero_scores = [s for s in all_scores if s['score'] > 0]
        sorted_high = sorted(all_scores, key=lambda x: x['score'], reverse=True)
        sorted_low = sorted(non_zero_scores, key=lambda x: x['score'])
        
        superlatives = {
            'highestScore': sorted_high[0] if sorted_high else None,
            'lowestScore': sorted_low[0] if sorted_low else None,
            'top10HighestScores': sorted_high[:10],
            'top10LowestScores': sorted_low[:10]
        }
        
        matchup_margins = []
        for m in matchups:
            if m['winner'] == 'TIE':
                continue
            
            margin = abs(m['home']['score'] - m['away']['score'])
            winner_data = m['home'] if m['winner'] == 'HOME' else m['away']
            loser_data = m['away'] if m['winner'] == 'HOME' else m['home']
            
            matchup_margins.append({
                'margin': margin,
                'winner': winner_data['teamName'],
                'winnerTeamId': winner_data['teamId'],
                'winnerScore': winner_data['score'],
                'loser': loser_data['teamName'],
                'loserScore': loser_data['score'],
                'year': m['year'],
                'week': m['week'],
                'matchupPeriodId': m['matchupPeriodId']
            })
        
        # Just keep it simple - no owner names needed
        if matchup_margins:
            superlatives['closestWin'] = min(matchup_margins, key=lambda x: x['margin'])
            superlatives['biggestBlowout'] = max(matchup_margins, key=lambda x: x['margin'])

        # For combined scoring, add owner names
        combined_scores = []
        for m in matchups:
            # Skip second week of 2-week playoff matchups
            if (m['year'], m['week']) in two_week_playoff_weeks:
                continue
                
            total = m['home']['score'] + m['away']['score']
            combined_scores.append({
                'total': total,
                'team1': m['home']['teamName'],
                'owner1': m['home']['owner'],
                'score1': m['home']['score'],
                'team2': m['away']['teamName'],
                'owner2': m['away']['owner'],
                'score2': m['away']['score'],
                'year': m['year'],
                'week': m['week'],
                'matchupPeriodId': m['matchupPeriodId']
            })
        
        non_zero_combined = [s for s in combined_scores if s['score1'] > 0 and s['score2'] > 0]
        
        superlatives['highestScoringGame'] = max(combined_scores, key=lambda x: x['total'])
        superlatives['lowestScoringGame'] = min(non_zero_combined, key=lambda x: x['total']) if non_zero_combined else None
        
        return superlatives
    
    def calculate_all_time_streaks(self, matchups):
        """Calculate longest win and loss streaks across all owners"""
        owner_games = defaultdict(list)
        for m in matchups:
            owner_games[m['home']['owner']].append({
                'year': m['year'],
                'week': m['week'],
                'won': m['winner'] == 'HOME',
                'lost': m['winner'] == 'AWAY',
                'teamName': m['home']['teamName']
            })
            owner_games[m['away']['owner']].append({
                'year': m['year'],
                'week': m['week'],
                'won': m['winner'] == 'AWAY',
                'lost': m['winner'] == 'HOME',
                'teamName': m['away']['teamName']
            })
        
        best_win, best_loss = self._compute_owner_streaks(owner_games)
        win_ties, win_length = self._streak_ties_at_max(best_win)
        loss_ties, loss_length = self._streak_ties_at_max(best_loss)

        empty_streak = {'owner': None, 'length': 0, 'teamName': None, 'startYear': None, 'startWeek': None, 'endYear': None, 'endWeek': None, 'isOngoing': False}

        longest_win_streak = {
            **(win_ties[0] if win_ties else empty_streak),
            'owners': win_ties,
            'tied': len(win_ties) > 1
        }
        longest_loss_streak = {
            **(loss_ties[0] if loss_ties else empty_streak),
            'owners': loss_ties,
            'tied': len(loss_ties) > 1
        }

        return {
            'longestWinStreak': longest_win_streak,
            'longestLossStreak': longest_loss_streak
        }

    def calculate_weekly_performance(self, matchups):
        """Calculate weekly high/low scorer stats and consolation dollars"""
        weekly_scores = defaultdict(list)
        for m in matchups:
            key = (m['year'], m['week'])
            weekly_scores[key].append({
                'owner': m['home']['owner'],
                'teamName': m['home']['teamName'],
                'score': m['home']['score'],
                'won': m['winner'] == 'HOME'
            })
            weekly_scores[key].append({
                'owner': m['away']['owner'],
                'teamName': m['away']['teamName'],
                'score': m['away']['score'],
                'won': m['winner'] == 'AWAY'
            })
        
        high_scorer_count = defaultdict(int)
        low_scorer_count = defaultdict(int)
        consolation_count = defaultdict(int)
        
        for (year, week), scores in weekly_scores.items():
            if not scores:
                continue
            
            sorted_scores = sorted(scores, key=lambda x: x['score'], reverse=True)
            
            highest = sorted_scores[0]
            high_scorer_count[highest['owner']] += 1
            
            lowest = sorted_scores[-1]
            low_scorer_count[lowest['owner']] += 1
            
            if len(sorted_scores) >= 2:
                second_highest = sorted_scores[1]
                if not second_highest['won']:
                    consolation_count[second_highest['owner']] += 1
        
        high_owners, high_count = self._counter_ties_at_max(high_scorer_count)
        low_owners, low_count = self._counter_ties_at_max(low_scorer_count)
        consolation_owners, consolation_count_val = self._counter_ties_at_max(consolation_count)

        return {
            'mostWeeklyHighScores': {
                'owner': high_owners[0] if high_owners else None,
                'owners': high_owners,
                'count': high_count,
                'tied': len(high_owners) > 1
            },
            'mostWeeklyLowScores': {
                'owner': low_owners[0] if low_owners else None,
                'owners': low_owners,
                'count': low_count,
                'tied': len(low_owners) > 1
            },
            'mostConsolationDollars': {
                'owner': consolation_owners[0] if consolation_owners else None,
                'owners': consolation_owners,
                'count': consolation_count_val,
                'tied': len(consolation_owners) > 1
            }
        }

    def calculate_seasonal_stats(self, matchups):
        """Calculate seasonal records like most points against (regular season only)"""
        season_stats = defaultdict(lambda: defaultdict(lambda: {'pointsAgainst': 0, 'teamName': None, 'owner': None}))
        
        # Only count regular season games
        for m in matchups:
            if m['isPlayoff']:
                continue
            
            home_owner = m['home'].get('owner')
            away_owner = m['away'].get('owner')
            
            # Skip if owner is missing
            if not home_owner or not away_owner:
                continue
                
            year = m['year']
            
            # Use owner as the key to avoid duplicate counting
            season_stats[home_owner][year]['pointsAgainst'] += m['away']['score']
            season_stats[home_owner][year]['teamName'] = m['home']['teamName']
            season_stats[home_owner][year]['owner'] = home_owner
            
            season_stats[away_owner][year]['pointsAgainst'] += m['home']['score']
            season_stats[away_owner][year]['teamName'] = m['away']['teamName']
            season_stats[away_owner][year]['owner'] = away_owner
        
        all_seasons = []
        for owner, years in season_stats.items():
            for year, stats in years.items():
                # Only add if we have valid data
                if stats['owner'] and stats['teamName']:
                    all_seasons.append({
                        'owner': owner,
                        'teamName': stats['teamName'],
                        'year': year,
                        'pointsAgainst': stats['pointsAgainst']
                    })
        
        sorted_high_pa = sorted(all_seasons, key=lambda x: x['pointsAgainst'], reverse=True)
        sorted_low_pa = sorted(all_seasons, key=lambda x: x['pointsAgainst'])
        
        # Debug print top 5
        print(f"  Top 5 highest PA seasons:")
        for i, s in enumerate(sorted_high_pa[:5]):
            print(f"    {i+1}. {s['owner']} ({s['teamName']}) - {s['year']}: {s['pointsAgainst']:.2f}")
        
        return {
            'mostPointsAgainstSeasons': sorted_high_pa[:5],
            'fewestPointsAgainstSeasons': sorted_low_pa[:5]
        }

    def calculate_season_stats(self, all_matchups, skip_bench=False, keepers_by_year=None, benchmarks_by_year=None):
        """Calculate stats for each individual season"""
        print(f"\n{'='*80}")
        print(" Calculating Season-by-Season Statistics")
        print(f"{'='*80}")
        
        # Calculate bench points (skip if flag is set)
        if skip_bench:
            print(f"  ⚠️  Skipping bench points calculation")
            bench_points = {}
        else:
            bench_points = self.calculate_bench_points_by_season(all_matchups)
        
        season_data = {}

        
        # Group matchups by year
        matchups_by_year = defaultdict(list)
        for m in all_matchups:
            matchups_by_year[m['year']].append(m)
        
        for year in sorted(matchups_by_year.keys()):
            year_matchups = matchups_by_year[year]
            regular_season = [m for m in year_matchups if not m['isPlayoff']]
            playoffs = [m for m in year_matchups if m['isPlayoff']]
            
            print(f"  Processing {year}...")
            
            # Basic superlatives for this season
            all_scores = []
            for m in year_matchups:
                all_scores.append({
                    'score': m['home']['score'],
                    'team': m['home']['teamName'],
                    'owner': m['home']['owner'],
                    'opponent': m['away']['teamName'],
                    'opponentScore': m['away']['score'],
                    'week': m['week'],
                    'matchupPeriodId': m['matchupPeriodId']
                })
                all_scores.append({
                    'score': m['away']['score'],
                    'team': m['away']['teamName'],
                    'owner': m['away']['owner'],
                    'opponent': m['home']['teamName'],
                    'opponentScore': m['home']['score'],
                    'week': m['week'],
                    'matchupPeriodId': m['matchupPeriodId']
                })
            
            sorted_scores = sorted(all_scores, key=lambda x: x['score'], reverse=True)
            non_zero = [s for s in all_scores if s['score'] > 0]
            sorted_low = sorted(non_zero, key=lambda x: x['score'])
            
            # Closest/biggest wins
            matchup_margins = []
            for m in year_matchups:
                if m['winner'] == 'TIE':
                    continue
                margin = abs(m['home']['score'] - m['away']['score'])
                winner_data = m['home'] if m['winner'] == 'HOME' else m['away']
                loser_data = m['away'] if m['winner'] == 'HOME' else m['home']
                matchup_margins.append({
                    'margin': margin,
                    'winner': winner_data['teamName'],
                    'winnerOwner': winner_data['owner'],
                    'winnerScore': winner_data['score'],
                    'loser': loser_data['teamName'],
                    'loserScore': loser_data['score'],
                    'week': m['week'],
                    'matchupPeriodId': m['matchupPeriodId']
                })
            
            # Streaks for this season
            owner_games = defaultdict(list)
            for m in year_matchups:
                owner_games[m['home']['owner']].append({
                    'week': m['week'],
                    'won': m['winner'] == 'HOME',
                    'lost': m['winner'] == 'AWAY',
                    'teamName': m['home']['teamName']
                })
                owner_games[m['away']['owner']].append({
                    'week': m['week'],
                    'won': m['winner'] == 'AWAY',
                    'lost': m['winner'] == 'HOME',
                    'teamName': m['away']['teamName']
                })

            season_best_win, season_best_loss = self._compute_owner_streaks(owner_games)
            season_win_ties, season_win_length = self._streak_ties_at_max(season_best_win)
            season_loss_ties, season_loss_length = self._streak_ties_at_max(season_best_loss)

            season_win_owners = [d['owner'] for d in season_win_ties]
            season_loss_owners = [d['owner'] for d in season_loss_ties]

            # Per-owner week ranges for linking - safe to build a simple
            # week-number list here (unlike the all-time version) since a
            # season-level streak never crosses a year boundary.
            season_win_streaks = [
                {'owner': d['owner'], 'weeks': list(range(d['startWeek'], d['endWeek'] + 1))}
                for d in season_win_ties
            ]
            season_loss_streaks = [
                {'owner': d['owner'], 'weeks': list(range(d['startWeek'], d['endWeek'] + 1))}
                for d in season_loss_ties
            ]

            longest_win = {
                'owner': season_win_owners[0] if season_win_owners else None,
                'length': season_win_length,
                'owners': season_win_owners,
                'tied': len(season_win_owners) > 1,
                'streaks': season_win_streaks
            }
            longest_loss = {
                'owner': season_loss_owners[0] if season_loss_owners else None,
                'length': season_loss_length,
                'owners': season_loss_owners,
                'tied': len(season_loss_owners) > 1,
                'streaks': season_loss_streaks
            }
            
            # Weekly high/low scorers
            weekly_scores = defaultdict(list)
            for m in regular_season:
                key = m['week']
                weekly_scores[key].append({
                    'owner': m['home']['owner'],
                    'team': m['home']['teamName'],
                    'score': m['home']['score'],
                    'won': m['winner'] == 'HOME'
                })
                weekly_scores[key].append({
                    'owner': m['away']['owner'],
                    'team': m['away']['teamName'],
                    'score': m['away']['score'],
                    'won': m['winner'] == 'AWAY'
                })

            high_scorer_count = defaultdict(int)
            low_scorer_count = defaultdict(int)
            consolation_count = defaultdict(int)

            # Weekly high score payouts - amounts changed over time
            weekly_high_payouts = []
            consolation_payouts = []

            # Determine weekly payout amount based on year
            if year == 2013:
                weekly_payout = 0  # No buy-in
            elif year == 2014:
                weekly_payout = 0  # Unconfirmed, skipping
            elif year in [2015, 2016, 2017, 2018, 2019]:
                weekly_payout = 5  # $5/week
            elif year == 2020:
                weekly_payout = 5  # $5/week with consolation dollar introduced
            elif year == 2021:
                weekly_payout = 5  # $5/week
            elif year == 2022:
                weekly_payout = 5  # $5/week
            else:  # 2023+
                weekly_payout = 10  # $10/week

            # Consolation dollar introduced in 2020
            has_consolation = year >= 2020

            for week, scores in weekly_scores.items():
                if not scores:
                    continue
                
                sorted_week = sorted(scores, key=lambda x: x['score'], reverse=True)
                highest = sorted_week[0]
                lowest = sorted_week[-1]
                
                high_scorer_count[highest['owner']] += 1
                low_scorer_count[lowest['owner']] += 1
                
                # Check for consolation dollar (only 2020+)
                consolation_this_week = False
                if has_consolation and len(sorted_week) >= 2:
                    second = sorted_week[1]
                    if not second['won']:  # 2nd highest lost
                        consolation_count[second['owner']] += 1
                        consolation_this_week = True
                        consolation_payouts.append({
                            'owner': second['owner'],
                            'team': second['team'],
                            'amount': 1,
                            'week': week,
                            'score': second['score']
                        })
                
                # Weekly high payout
                if weekly_payout > 0:
                    payout_amount = (weekly_payout - 1) if consolation_this_week else weekly_payout
                    weekly_high_payouts.append({
                        'owner': highest['owner'],
                        'team': highest['team'],
                        'amount': payout_amount,
                        'week': week,
                        'score': highest['score']
                    })

            # NOW calculate the most values AFTER the loop
            season_high_owners, season_high_count = self._counter_ties_at_max(high_scorer_count)
            season_low_owners, season_low_count = self._counter_ties_at_max(low_scorer_count)
            season_consolation_owners, season_consolation_count = self._counter_ties_at_max(consolation_count)

            # Playoff payouts - amounts changed over time
            playoff_payouts = []
            season_league = next((s['league'] for s in self.all_seasons if s['year'] == year), None)

            # Determine playoff payouts based on year
            if year == 2013:
                playoff_amounts = {'1st': 0, '2nd': 0, '3rd': 0}  # No buy-in
            elif year == 2014:
                playoff_amounts = {'1st': 35, '2nd': 15, '3rd': 10}  # Unconfirmed but documented
            elif year == 2015:
                playoff_amounts = {'1st': 109, '2nd': 60, '3rd': 31}
            elif year in [2016, 2017, 2018, 2019, 2020]:
                playoff_amounts = {'1st': 150, '2nd': 70, '3rd': 40}
            elif year in [2021, 2022]:
                playoff_amounts = {'1st': 185, '2nd': 90, '3rd': 50}
            else:  # 2023+
                playoff_amounts = {'1st': 210, '2nd': 100, '3rd': 50}

            if season_league:
                members = {}
                if hasattr(season_league, 'members') and season_league.members:
                    try:
                        if hasattr(season_league.members, 'items'):
                            members = season_league.members
                        else:
                            members = {m.id: m for m in season_league.members}
                    except (AttributeError, TypeError):
                        pass
                
                for team in season_league.teams:
                    owner = self.get_owner_name_from_team(team, members)
                    if hasattr(team, 'final_standing') and team.final_standing:
                        if team.final_standing == 1:
                            playoff_payouts.append({
                                'owner': owner,
                                'team': team.team_name,
                                'amount': playoff_amounts['1st'],
                                'place': '1st'
                            })
                        elif team.final_standing == 2:
                            playoff_payouts.append({
                                'owner': owner,
                                'team': team.team_name,
                                'amount': playoff_amounts['2nd'],
                                'place': '2nd'
                            })
                        elif team.final_standing == 3:
                            playoff_payouts.append({
                                'owner': owner,
                                'team': team.team_name,
                                'amount': playoff_amounts['3rd'],
                                'place': '3rd'
                            })

            season_data[year] = {
                'year': year,
                'highestScore': sorted_scores[0] if sorted_scores else None,
                'lowestScore': sorted_low[0] if sorted_low else None,
                'closestWin': min(matchup_margins, key=lambda x: x['margin']) if matchup_margins else None,
                'biggestBlowout': max(matchup_margins, key=lambda x: x['margin']) if matchup_margins else None,
                'longestWinStreak': longest_win,
                'longestLossStreak': longest_loss,
                'mostWeeklyHighScores': {
                    'owner': season_high_owners[0] if season_high_owners else None,
                    'owners': season_high_owners,
                    'count': season_high_count,
                    'tied': len(season_high_owners) > 1
                },
                'mostWeeklyLowScores': {
                    'owner': season_low_owners[0] if season_low_owners else None,
                    'owners': season_low_owners,
                    'count': season_low_count,
                    'tied': len(season_low_owners) > 1
                },
                'mostConsolationDollars': {
                    'owner': season_consolation_owners[0] if season_consolation_owners else None,
                    'owners': season_consolation_owners,
                    'count': season_consolation_count,
                    'tied': len(season_consolation_owners) > 1
                },
                'bestBenchWarmers': bench_points.get(year),
                'weeklyHighPayouts': weekly_high_payouts,
                'consolationPayouts': consolation_payouts,
                'playoffPayouts': playoff_payouts,
                'keeperAnalysis': {
                    'keepers':         (keepers_by_year or {}).get(year, []),
                    'roundBenchmarks': (benchmarks_by_year or {}).get(year, {}),
                },
            }
        
        return season_data

    def calculate_player_loyalty_stats(self, owner_stats):
        """Calculate which player each owner rostered the most seasons"""
        print(f"\n  Calculating player loyalty stats...")
        
        loyalty_stats = {}
        
        for season_data in self.all_seasons:
            year = season_data['year']
            league = season_data['league']
            
            members = {}
            if hasattr(league, 'members') and league.members:
                try:
                    if hasattr(league.members, 'items'):
                        members = league.members
                    else:
                        members = {m.id: m for m in league.members}
                except (AttributeError, TypeError):
                    pass
            
            for team in league.teams:
                owner = self.get_owner_name_from_team(team, members)
                if not owner or owner not in owner_stats:
                    continue
                
                if owner not in loyalty_stats:
                    loyalty_stats[owner] = defaultdict(list)
                
                # Track all players on roster
                for player in team.roster:
                    player_name = player.name
                    loyalty_stats[owner][player_name].append(year)
        
        # Find most loyal player for each owner
        for owner in loyalty_stats:
            player_seasons = {player: len(years) for player, years in loyalty_stats[owner].items()}
            if player_seasons:
                most_loyal_player = max(player_seasons.items(), key=lambda x: x[1])
                owner_stats[owner]['mostLoyalPlayer'] = most_loyal_player[0]
                owner_stats[owner]['mostLoyalPlayerSeasons'] = most_loyal_player[1]
                owner_stats[owner]['mostLoyalPlayerYears'] = sorted(loyalty_stats[owner][most_loyal_player[0]])
            else:
                owner_stats[owner]['mostLoyalPlayer'] = None
                owner_stats[owner]['mostLoyalPlayerSeasons'] = 0
        
        return owner_stats
        
    def calculate_bench_points_by_season(self, all_matchups):
        """Calculate bench points for each team by season"""
        print(f"\n  Calculating bench points by season...")
        
        bench_points_by_season = {}
        
        for season_data in self.all_seasons:
            year = season_data['year']
            league = season_data['league']
            
            # Skip years before 2019 (bench data not reliable)
            if year < 2019:
                continue
            
            print(f"    Processing {year} bench scores...")
            
            members = {}
            if hasattr(league, 'members') and league.members:
                try:
                    if hasattr(league.members, 'items'):
                        members = league.members
                    else:
                        members = {m.id: m for m in league.members}
                except (AttributeError, TypeError):
                    pass
            
            year_bench_points = {}
            
            # Get regular season week count
            reg_season_weeks = getattr(league.settings, 'reg_season_count', 14)
            reg_season_weeks = self._completed_weeks(league, reg_season_weeks)
            
            for team in league.teams:
                owner = self.get_owner_name_from_team(team, members)
                if not owner:
                    continue
                
                total_bench_points = 0
                
                # Go through each week of regular season
                for week in range(1, reg_season_weeks + 1):
                    try:
                        box_scores = league.box_scores(week)
                        for box in box_scores:
                            if box.home_team.team_id == team.team_id:
                                # Sum bench points
                                if hasattr(box, 'home_lineup') and box.home_lineup:
                                    for player in box.home_lineup:
                                        if hasattr(player, 'slot_position') and player.slot_position == 'BE':
                                            total_bench_points += getattr(player, 'points', 0)
                                break
                            elif box.away_team.team_id == team.team_id:
                                if hasattr(box, 'away_lineup') and box.away_lineup:
                                    for player in box.away_lineup:
                                        if hasattr(player, 'slot_position') and player.slot_position == 'BE':
                                            total_bench_points += getattr(player, 'points', 0)
                                break
                    except Exception as e:
                        # Skip this week if there's an error
                        continue
                
                if total_bench_points > 0:
                    year_bench_points[owner] = {
                        'owner': owner,
                        'teamName': team.team_name,
                        'benchPoints': total_bench_points
                    }
            
            if year_bench_points:
                best_bench = max(year_bench_points.values(), key=lambda x: x['benchPoints'])
                bench_points_by_season[year] = best_bench
                print(f"      ✓ Best bench: {best_bench['owner']} - {best_bench['benchPoints']:.2f} pts")
            else:
                bench_points_by_season[year] = None
                print(f"      ✗ No bench data available")
        
        return bench_points_by_season

    def analyze_rosters_and_trades(self):
        """Analyze draft performance, trades, and roster moves"""
        print(f"\n{'='*80}")
        print(" Analyzing Rosters, Trades & Draft Performance")
        print(f"{'='*80}")
        
        all_trades = []
        draft_analysis = {}
        
        for season_data in self.all_seasons:
            year = season_data['year']
            league = season_data['league']
            
            print(f"  Processing {year}...")
            
            members = {}
            if hasattr(league, 'members') and league.members:
                try:
                    if hasattr(league.members, 'items'):
                        members = league.members
                    else:
                        members = {m.id: m for m in league.members}
                except (AttributeError, TypeError):
                    pass
            
            # Track trades
            try:
                activities = league.recent_activity()
                if activities:
                    for activity in activities:
                        try:
                            if hasattr(activity, 'actions') and len(activity.actions) == 2:
                                action1, action2 = activity.actions
                                
                                if hasattr(action1, 'team') and hasattr(action2, 'team'):
                                    team1_owner = self.get_owner_name_from_team(action1.team, members)
                                    team2_owner = self.get_owner_name_from_team(action2.team, members)
                                    
                                    trade_data = {
                                        'year': year,
                                        'date': str(activity.date) if hasattr(activity, 'date') else None,
                                        'team1': {
                                            'owner': team1_owner,
                                            'teamName': action1.team.team_name,
                                            'playersOut': [],
                                            'playersIn': []
                                        },
                                        'team2': {
                                            'owner': team2_owner,
                                            'teamName': action2.team.team_name,
                                            'playersOut': [],
                                            'playersIn': []
                                        }
                                    }
                                    
                                    # Parse players
                                    if hasattr(action1, 'player') and action1.player:
                                        trade_data['team1']['playersOut'].append(action1.player.name)
                                        trade_data['team2']['playersIn'].append(action1.player.name)
                                    
                                    if hasattr(action2, 'player') and action2.player:
                                        trade_data['team2']['playersOut'].append(action2.player.name)
                                        trade_data['team1']['playersIn'].append(action2.player.name)
                                    
                                    all_trades.append(trade_data)
                        except Exception as e:
                            # Skip this activity if there's an error
                            continue
            except Exception as e:
                print(f"    ⚠️  Could not fetch trade data: {e}")
            
            # Draft performance analysis for most recent season only
            if year == self.end_year:
                try:
                    reg_season_weeks = getattr(league.settings, 'reg_season_count', 14)
                    
                    for team in league.teams:
                        owner = self.get_owner_name_from_team(team, members)
                        if not owner:
                            continue
                        
                        # Get draft picks
                        drafted_players = {}
                        try:
                            if hasattr(league, 'draft') and league.draft:
                                for pick in league.draft:
                                    if pick.team.team_id == team.team_id:
                                        drafted_players[pick.playerName] = {
                                            'name': pick.playerName,
                                            'round': pick.round_num,
                                            'pick': pick.round_pick,
                                            'keptToPlayoffs': False,
                                            'totalPoints': 0
                                        }
                        except Exception as e:
                            print(f"    ⚠️  Could not fetch draft data for {owner}: {e}")
                        
                        drafted_kept = 0
                        drafted_points = 0
                        waiver_count = 0
                        waiver_points = 0
                        
                        for player in team.roster:
                            player_name = player.name
                            
                            # Check if this was a drafted player
                            if player_name in drafted_players:
                                drafted_players[player_name]['keptToPlayoffs'] = True
                                drafted_players[player_name]['totalPoints'] = getattr(player, 'total_points', 0)
                                drafted_kept += 1
                                drafted_points += getattr(player, 'total_points', 0)
                            else:
                                # This is a waiver pickup
                                waiver_count += 1
                                waiver_points += getattr(player, 'total_points', 0)
                        
                        draft_analysis[owner] = {
                            'owner': owner,
                            'teamName': team.team_name,
                            'totalDrafted': len(drafted_players),
                            'draftedKeptToPlayoffs': drafted_kept,
                            'draftedPointsScored': drafted_points,
                            'waiverPickups': waiver_count,
                            'waiverPointsScored': waiver_points,
                            'draftRetentionRate': (drafted_kept / len(drafted_players) * 100) if drafted_players else 0,
                            'draftedPlayers': list(drafted_players.values())
                        }
                except Exception as e:
                    print(f"    ⚠️  Could not analyze 2025 draft: {e}")
        
        print(f"  ✓ Found {len(all_trades)} trades")
        print(f"  ✓ Analyzed draft for {len(draft_analysis)} teams")
        
        return {
            'trades': all_trades,
            f'draft_analysis_{self.end_year}': draft_analysis
        }

    def analyze_two_week_playoff_comebacks(self, all_matchups):
        """Analyze 2-week playoff matchups to see how many were won because of week 2"""
        print(f"\n{'='*80}")
        print(" Analyzing Two-Week Playoff Comebacks")
        print(f"{'='*80}")
        
        try:
            # Find all 2-week playoff matchups
            playoff_matchups = [m for m in all_matchups if m['isPlayoff']]
            
            # Group by year and matchup
            two_week_matchups = {}
            
            for m in playoff_matchups:
                # Look for consecutive weeks with same teams
                for m2 in playoff_matchups:
                    if (m2['year'] == m['year'] and 
                        m2['week'] == m['week'] + 1 and
                        ((m2['home']['teamId'] == m['home']['teamId'] and m2['away']['teamId'] == m['away']['teamId']) or
                         (m2['home']['teamId'] == m['away']['teamId'] and m2['away']['teamId'] == m['home']['teamId']))):
                        
                        # Found a 2-week matchup
                        matchup_key = f"{m['year']}_week{m['week']}-{m2['week']}"
                        
                        if matchup_key not in two_week_matchups:
                            # Determine which team is which across both weeks
                            if m['home']['teamId'] == m2['home']['teamId']:
                                team_a_id = m['home']['teamId']
                                team_a_name = m['home']['teamName']
                                team_a_owner = m['home']['owner']
                                team_b_id = m['away']['teamId']
                                team_b_name = m['away']['teamName']
                                team_b_owner = m['away']['owner']
                                week1_team_a_score = m['home']['score']
                                week1_team_b_score = m['away']['score']
                                week2_team_a_score = m2['home']['score']
                                week2_team_b_score = m2['away']['score']
                            else:
                                team_a_id = m['home']['teamId']
                                team_a_name = m['home']['teamName']
                                team_a_owner = m['home']['owner']
                                team_b_id = m['away']['teamId']
                                team_b_name = m['away']['teamName']
                                team_b_owner = m['away']['owner']
                                week1_team_a_score = m['home']['score']
                                week1_team_b_score = m['away']['score']
                                week2_team_a_score = m2['away']['score']
                                week2_team_b_score = m2['home']['score']
                            
                            # Calculate totals
                            team_a_total = week1_team_a_score + week2_team_a_score
                            team_b_total = week1_team_b_score + week2_team_b_score
                            
                            # Determine if there was a comeback
                            week1_leader = 'team_a' if week1_team_a_score > week1_team_b_score else 'team_b'
                            final_winner = 'team_a' if team_a_total > team_b_total else 'team_b'
                            
                            comeback = (week1_leader != final_winner)
                            
                            two_week_matchups[matchup_key] = {
                                'year': m['year'],
                                'week1': m['week'],
                                'week2': m2['week'],
                                'teamA': {
                                    'name': team_a_name,
                                    'owner': team_a_owner,
                                    'week1Score': week1_team_a_score,
                                    'week2Score': week2_team_a_score,
                                    'totalScore': team_a_total
                                },
                                'teamB': {
                                    'name': team_b_name,
                                    'owner': team_b_owner,
                                    'week1Score': week1_team_b_score,
                                    'week2Score': week2_team_b_score,
                                    'totalScore': team_b_total
                                },
                                'week1Leader': week1_leader,
                                'finalWinner': final_winner,
                                'comeback': comeback,
                                'week1Margin': abs(week1_team_a_score - week1_team_b_score),
                                'finalMargin': abs(team_a_total - team_b_total)
                            }
            
            comebacks = [m for m in two_week_matchups.values() if m['comeback']]
            
            print(f"  ✓ Found {len(two_week_matchups)} two-week playoff matchups")
            print(f"  ✓ {len(comebacks)} comebacks (losing after week 1 but won overall)")
            if two_week_matchups:
                print(f"  ✓ Comeback rate: {len(comebacks) / len(two_week_matchups) * 100:.1f}%")
            
            return {
                'totalTwoWeekMatchups': len(two_week_matchups),
                'comebacks': len(comebacks),
                'comebackRate': len(comebacks) / len(two_week_matchups) if two_week_matchups else 0,
                'matchups': list(two_week_matchups.values()),
                'comebackMatchups': comebacks
            }
        except Exception as e:
            print(f"  ✗ Error analyzing two-week playoffs: {e}")
            return {
                'totalTwoWeekMatchups': 0,
                'comebacks': 0,
                'comebackRate': 0,
                'matchups': [],
                'comebackMatchups': []
            }

    def _completed_weeks(self, league, requested_weeks):
        """Cap a per-week loop at the number of weeks that have actually
        started this season, per league.current_week.

        ESPN's per-week endpoints do not reliably return empty data for
        weeks beyond the season's current live week. Confirmed directly
        in the espn-api library source (box_scores()): if the requested
        week is greater than league.current_week, the method silently
        keeps querying the CURRENT scoring/matchup period instead of the
        requested one - it does not raise, return empty, or signal
        anything is wrong. The raw mTransactions2 endpoint (used by
        transactions()) shows the same symptom: querying a future
        scoringPeriodId echoes back current-period data rather than an
        empty list.

        Net effect if this isn't guarded: looping range(1, total_weeks+1)
        for the current in-progress season doesn't skip unplayed weeks -
        it duplicates the current week's real games/transactions once
        per remaining week number. Confirmed empirically in Week 1 of
        the 2026 season (The Other League): fake 17-0 season records and
        a single real drop inflated to 17x in the most-dropped-players
        stat. Same loop shape exists in this collector, so the fix is
        applied here too even though MMT hasn't hit the symptom yet.

        For a completed past season, league.current_week reflects that
        season's final week, so this cap is a no-op there - it only
        changes behavior for the current, still-in-progress season.
        """
        current_week = getattr(league, 'current_week', None)
        if not current_week or current_week <= 0:
            return requested_weeks
        return min(requested_weeks, current_week)

    def _direct_api(self, year, view, extra_params=""):
        """
        Make a direct request to the ESPN leagueHistory endpoint.
        Returns the unwrapped response dict, or None on failure.
        """
        url = (
            f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
            f"/leagueHistory/{self.league_id}?seasonId={year}&view={view}{extra_params}"
        )
        cookies = {"SWID": self.swid, "espn_s2": self.espn_s2}
        headers = {"Accept": "application/json"}
        try:
            resp = requests.get(url, cookies=cookies, headers=headers, timeout=20)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data[0] if isinstance(data, list) and data else data
        except Exception as e:
            print(f"    ✗ Direct API error ({year} {view}): {e}")
            return None

    def _normalize_name(self, name):
        """Lowercase + strip punctuation for fuzzy player name matching."""
        import re
        return re.sub(r"[^a-z0-9 ]", "", name.lower().strip())

    def _title_case_owner(self, name):
        """Ensure owner names are consistently title-cased."""
        if not name:
            return name
        return " ".join(w.capitalize() for w in name.strip().split())

    def _get_player_points_weekly(self, year, reg_season_weeks):
        """
        For years where mRoster appliedStatTotal is zeroed (2018),
        reconstruct per-player season totals by summing weekly
        appliedStatTotal across all regular season scoring periods.

        Returns:
            player_points: { playerId: { name, points, teamId,
                                         droppedMidSeason, lastActiveWeek } }
        """
        # player_id -> { name, teamId, weekly: {week: points} }
        weekly_tracker = {}

        for week in range(1, reg_season_weeks + 1):
            week_data = self._direct_api(
                year, "mRoster",
                extra_params=f"&scoringPeriodId={week}"
            )
            if not week_data:
                continue
            for team in week_data.get("teams", []):
                team_id = team.get("id")
                for entry in team.get("roster", {}).get("entries", []):
                    pool   = entry.get("playerPoolEntry", {})
                    pid    = pool.get("id") or entry.get("playerId")
                    pts    = pool.get("appliedStatTotal", 0.0) or 0.0
                    name   = pool.get("player", {}).get("fullName", "")
                    if pid not in weekly_tracker:
                        weekly_tracker[pid] = {
                            "name":   name,
                            "teamId": team_id,
                            "weekly": {}
                        }
                    # Only update name/teamId from the first week we see them
                    if not weekly_tracker[pid]["name"] and name:
                        weekly_tracker[pid]["name"] = name
                    weekly_tracker[pid]["weekly"][week] = pts

        # Collapse to season totals + drop detection
        player_points = {}
        for pid, info in weekly_tracker.items():
            weekly = info["weekly"]
            season_total = sum(weekly.values())
            weeks_with_points = [w for w, p in weekly.items() if p > 0]
            last_active = max(weeks_with_points) if weeks_with_points else 0
            dropped = (
                last_active > 0 and
                last_active < reg_season_weeks and
                all(weekly.get(w, 0) == 0
                    for w in range(last_active + 1, reg_season_weeks + 1))
            )
            player_points[pid] = {
                "name":            info["name"],
                "points":          round(season_total, 2),
                "teamId":          info["teamId"],
                "droppedMidSeason": dropped,
                "lastActiveWeek":  last_active if dropped else None,
            }
        return player_points

    def _get_player_points_weekly_via_boxscore(self, year, reg_season_weeks):
        """
        Fallback for years where mRoster's appliedStatTotal is broken at
        the player level (confirmed for 2017 in the TOT sibling league —
        mRoster returns 0.0 for every player every week, but mBoxscore's
        rosterForMatchupPeriod carries real per-player point values).

        IMPORTANT CAVEAT: mBoxscore's rosterForMatchupPeriod only includes
        players in active (non-bench) lineup slots for that matchup, not
        the full roster. This means:
          - A player's score is only captured for weeks they started.
          - We CANNOT distinguish "benched this week" from "not yet
            rostered" or "dropped" the way the mRoster-based sweep can,
            since bench players simply don't appear here at all.
          - droppedMidSeason / lastActiveWeek from this method should be
            treated as "last week we saw them START", not a true drop
            date. A keeper benched for the second half of the season will
            look identical to one who was dropped — this is a real
            information loss, not just a quirk of the method. If a
            specific keeper's verdict looks suspicious, verify manually
            rather than trusting this distinction for 2017 data.

        Returns same shape as _get_player_points_weekly.
        """
        weekly_tracker = {}

        for week in range(1, reg_season_weeks + 1):
            week_data = self._direct_api(
                year, "mBoxscore",
                extra_params=f"&scoringPeriodId={week}"
            )
            if not week_data:
                continue
            for matchup in week_data.get("schedule", []):
                for side in ("home", "away"):
                    team_side = matchup.get(side, {})
                    team_id = team_side.get("teamId")
                    roster = team_side.get("rosterForMatchupPeriod", {})
                    for entry in roster.get("entries", []):
                        pool = entry.get("playerPoolEntry", {})
                        pid  = pool.get("id") or entry.get("playerId")
                        pts  = pool.get("appliedStatTotal", 0.0) or 0.0
                        name = pool.get("player", {}).get("fullName", "")
                        if pid not in weekly_tracker:
                            weekly_tracker[pid] = {
                                "name":   name,
                                "teamId": team_id,
                                "weekly": {}
                            }
                        if not weekly_tracker[pid]["name"] and name:
                            weekly_tracker[pid]["name"] = name
                        weekly_tracker[pid]["weekly"][week] = pts

        player_points = {}
        for pid, info in weekly_tracker.items():
            weekly = info["weekly"]
            season_total = sum(weekly.values())
            weeks_seen = sorted(weekly.keys())
            last_active = max(weeks_seen) if weeks_seen else 0
            # See caveat above: "dropped" here really means "stopped
            # appearing in the active lineup", which conflates benching
            # with dropping. Flagged as droppedMidSeason so the season
            # stats page can still show a note, but it is a weaker signal
            # than the mRoster-based version used for 2018+.
            dropped = (
                last_active > 0 and last_active < reg_season_weeks
            )
            player_points[pid] = {
                "name":            info["name"],
                "points":          round(season_total, 2),
                "teamId":          info["teamId"],
                "droppedMidSeason": dropped,
                "lastActiveWeek":  last_active if dropped else None,
            }
        return player_points

    def _get_player_points_with_fallback(self, year, player_points,
                                         pid, norm_name, reg_season_weeks):
        """
        For a specific keeper showing zero or missing points, do a targeted
        weekly sweep to get their real season contribution even if dropped.

        Returns updated { points, droppedMidSeason, lastActiveWeek } or None.
        """
        weekly_scores = {}
        found_name    = ""

        for week in range(1, reg_season_weeks + 1):
            week_data = self._direct_api(
                year, "mRoster",
                extra_params=f"&scoringPeriodId={week}"
            )
            if not week_data:
                continue
            for team in week_data.get("teams", []):
                for entry in team.get("roster", {}).get("entries", []):
                    pool  = entry.get("playerPoolEntry", {})
                    e_pid = pool.get("id") or entry.get("playerId")
                    e_name = pool.get("player", {}).get("fullName", "")
                    # Match by ID if we have it, otherwise by name
                    match = (pid and e_pid == pid) or (
                        not pid and
                        self._normalize_name(e_name) == norm_name
                    )
                    if match:
                        pts = pool.get("appliedStatTotal", 0.0) or 0.0
                        weekly_scores[week] = pts
                        if not found_name and e_name:
                            found_name = e_name
                        if not pid:
                            pid = e_pid
                        break

        # If mRoster found the player but every week is exactly zero, this
        # may be the same player-level mRoster bug seen in 2017 rather than
        # a genuinely zero-scoring player — try mBoxscore before giving up.
        all_zero = bool(weekly_scores) and all(v == 0 for v in weekly_scores.values())
        if not weekly_scores or all_zero:
            box_weekly = {}
            for week in range(1, reg_season_weeks + 1):
                week_data = self._direct_api(
                    year, "mBoxscore",
                    extra_params=f"&scoringPeriodId={week}"
                )
                if not week_data:
                    continue
                for matchup in week_data.get("schedule", []):
                    for side in ("home", "away"):
                        roster = matchup.get(side, {}).get("rosterForMatchupPeriod", {})
                        for entry in roster.get("entries", []):
                            pool   = entry.get("playerPoolEntry", {})
                            e_pid  = pool.get("id") or entry.get("playerId")
                            e_name = pool.get("player", {}).get("fullName", "")
                            match = (pid and e_pid == pid) or (
                                not pid and
                                self._normalize_name(e_name) == norm_name
                            )
                            if match:
                                box_weekly[week] = pool.get("appliedStatTotal", 0.0) or 0.0
                                if not found_name and e_name:
                                    found_name = e_name
                                if not pid:
                                    pid = e_pid
            # Only prefer the mBoxscore result if it actually found
            # non-zero data the mRoster sweep didn't.
            if box_weekly and any(v != 0 for v in box_weekly.values()):
                weekly_scores = box_weekly

        if not weekly_scores:
            return None, found_name

        season_total     = sum(weekly_scores.values())
        weeks_with_points = [w for w, p in weekly_scores.items() if p > 0]
        last_active      = max(weeks_with_points) if weeks_with_points else 0
        dropped          = (
            last_active > 0 and
            last_active < reg_season_weeks and
            all(weekly_scores.get(w, 0) == 0
                for w in range(last_active + 1, reg_season_weeks + 1))
        )

        return {
            "points":           round(season_total, 2),
            "droppedMidSeason": dropped,
            "lastActiveWeek":   last_active if dropped else None,
        }, found_name

    def fetch_keeper_data_by_year(self):
        """
        Build unified keeper dataset covering 2017 through the most recent
        completed season (self.end_year).
        (2016 excluded — chaotic draft that year, no reliable keeper records)

        2017-2021: player identity from KEEPER_DATA constant.
            2018-2021: weekly mRoster sweep (end-of-season snapshot is zeroed
                        for 2018 specifically; the sweep runs for all of
                        these years regardless).
            2017:       mRoster returns all-zero appliedStatTotal for every
                        player, every week — not just a stale end-of-season
                        snapshot issue. The sweep auto-detects an all-zero
                        result (same mechanism used in the TOT sibling
                        league) and falls back to
                        _get_player_points_weekly_via_boxscore, which
                        reconstructs points from mBoxscore's
                        rosterForMatchupPeriod instead. That fallback only
                        sees active (non-bench) lineup slots, so
                        droppedMidSeason/lastActiveWeek for 2017 should be
                        treated as approximate (see that method's docstring).
            All:        zero-point keepers get a targeted weekly fallback to
                        capture mid-season drops (injuries, holdouts, etc.)
                        via _get_player_points_with_fallback, which itself
                        tries mBoxscore if mRoster finds nothing.

        2022+: player identity from mDraftDetail keeper flag;
               end-of-season mRoster for points; same zero fallback.

        NOTE: this queries the leagueHistory endpoint, which historically
        only serves completed seasons. It has never been run against a
        still-in-progress current season before (self.end_year previously
        always pointed at a season that had already ended by the time this
        ran) - if 2026's draft board isn't available there yet mid-season,
        this will print "Could not fetch mDraftDetail" and skip 2026 rather
        than fail, but that's an untested situation worth watching the
        first time this runs during an active season.

        Round benchmarks: average points scored by all non-keeper drafted
        players in the same round, giving a fair "expected value" baseline.

        Returns:
            keepers_by_year:    { year: [ keeperEntry, ... ] }
            benchmarks_by_year: { year: { round_int: avg_points } }
        """
        import re

        print(f"\n{'='*80}")
        print(" Fetching Keeper Data & Round Benchmarks")
        print(f"{'='*80}")

        VERDICT_THRESHOLD = 0.20   # ±20% vs round average = STEAL / BUST

        # 2017 is earliest year with usable data (via mBoxscore fallback);
        # 2016 is excluded due to a chaotic draft with no reliable records.
        FIRST_KEEPER_YEAR  = 2017

        keepers_by_year    = {}
        benchmarks_by_year = {}

        for year in range(FIRST_KEEPER_YEAR, self.end_year + 1):
            print(f"\n  Processing {year}...")

            # ── Get teamId -> owner mapping from already-fetched league ───
            season_obj = next(
                (s for s in self.all_seasons if s['year'] == year), None
            )
            team_id_to_owner = {}
            reg_season_weeks = 13   # safe default
            if season_obj:
                league = season_obj['league']
                members = {}
                if hasattr(league, 'members') and league.members:
                    try:
                        members = (
                            league.members
                            if hasattr(league.members, 'items')
                            else {m.id: m for m in league.members}
                        )
                    except (AttributeError, TypeError):
                        pass
                for team in league.teams:
                    owner = self.get_owner_name_from_team(team, members)
                    if owner:
                        team_id_to_owner[team.team_id] = (
                            self._title_case_owner(owner)
                        )
                reg_season_weeks = getattr(
                    league.settings, 'reg_season_count', 13
                )
                reg_season_weeks = self._completed_weeks(league, reg_season_weeks)

            # ── 1. Fetch draft board ──────────────────────────────────────
            draft_data = self._direct_api(year, "mDraftDetail")
            if not draft_data:
                print(f"    ✗ Could not fetch mDraftDetail for {year}, skipping")
                continue

            picks = draft_data.get("draftDetail", {}).get("picks", [])
            if not picks:
                print(f"    ✗ No draft picks returned for {year}, skipping")
                continue

            # playerId -> { round, pick, teamId, keeper, keeperValue }
            draft_by_pid  = {}
            # normalized name -> playerId  (fallback for hardcoded keepers)
            pid_by_name   = {}
            for pick in picks:
                pid  = pick.get("playerId")
                rnd  = pick.get("roundId")
                entry = {
                    "round":       rnd,
                    "pick":        pick.get("roundPickNumber"),
                    "teamId":      pick.get("teamId"),
                    "keeper":      pick.get("keeper", False),
                    # keeperValue = the round slot consumed (may differ from roundId)
                    "keeperValue": pick.get("keeperValue") or rnd,
                }
                if pid:
                    draft_by_pid[pid] = entry
                    # ESPN doesn't return playerName in leagueHistory draft picks,
                    # so we populate pid_by_name from player_points after roster fetch
            print(f"    ✓ Draft board: {len(picks)} picks")

            # ── 2. Fetch player points via weekly sweep ───────────────────
            # appliedStatTotal on end-of-season mRoster returns only the LAST
            # scoring period's score, not a season total — unusable for our
            # purposes. Weekly sweep is required for all years.
            print(f"    Sweeping {reg_season_weeks} weeks for player points...")
            player_points = self._get_player_points_weekly(
                year, reg_season_weeks
            )

            non_zero = sum(1 for p in player_points.values() if p['points'] > 0)
            print(f"    ✓ Player points: {len(player_points)} players, "
                  f"{non_zero} with non-zero totals")

            # mRoster's appliedStatTotal is broken at the player level for
            # some historical seasons (confirmed for 2017 in the TOT sibling
            # league, even though mBoxscore's per-team totals for the same
            # weeks are correct). If the mRoster sweep comes back essentially
            # empty, fall back to reconstructing points from mBoxscore.
            # See _get_player_points_weekly_via_boxscore for the caveat
            # this introduces around drop/bench detection.
            if player_points and non_zero == 0:
                print(f"    ⚠️  mRoster returned all-zero player points for "
                      f"{year} — falling back to mBoxscore sweep...")
                player_points = self._get_player_points_weekly_via_boxscore(
                    year, reg_season_weeks
                )
                non_zero = sum(1 for p in player_points.values() if p['points'] > 0)
                print(f"    ✓ Player points (via mBoxscore): {len(player_points)} players, "
                      f"{non_zero} with non-zero totals")

            # Build name->pid lookup from the player_points we just fetched
            for p_pid, p_info in player_points.items():
                n = self._normalize_name(p_info["name"])
                if n:
                    pid_by_name[n] = p_pid

            # ── 3. Build round benchmarks ─────────────────────────────────
            # Use only non-keeper drafted players for a fair baseline
            round_totals = defaultdict(list)
            for p_pid, p_info in player_points.items():
                draft_info = draft_by_pid.get(p_pid)
                if not draft_info:
                    continue
                if draft_info["keeper"]:
                    continue          # exclude keepers from their own benchmark
                rnd = draft_info["round"]
                pts = p_info["points"]
                if rnd and pts > 0:
                    round_totals[rnd].append(pts)

            benchmarks = {
                rnd: round(sum(pts) / len(pts), 2)
                for rnd, pts in round_totals.items()
                if pts
            }
            benchmarks_by_year[year] = benchmarks
            print(f"    ✓ Benchmarks: {len(benchmarks)} rounds, "
                  f"{sum(len(v) for v in round_totals.values())} players")

            # ── 4. Identify raw keepers ───────────────────────────────────
            raw_keepers = []

            if year <= 2021:
                # Identity from KEEPER_DATA; playerId resolved via pid_by_name
                for owner, keeper_list in KEEPER_DATA.get(year, {}).items():
                    owner = self._title_case_owner(owner)
                    for player_name, round_kept in keeper_list:
                        norm = self._normalize_name(player_name)
                        resolved_pid = pid_by_name.get(norm)
                        raw_keepers.append({
                            "owner":     owner,
                            "player":    player_name,
                            "roundKept": round_kept,
                            "playerId":  resolved_pid,
                        })
            else:
                # Identity from draft board keeper flag
                for pick in picks:
                    if not pick.get("keeper", False):
                        continue
                    pid     = pick.get("playerId")
                    tid     = pick.get("teamId")
                    round_k = pick.get("keeperValue") or pick.get("roundId")
                    owner   = self._title_case_owner(
                        team_id_to_owner.get(tid, f"Team {tid}")
                    )
                    # Resolve name: player_points roster first, then draft pick
                    p_name = ""
                    if pid and pid in player_points:
                        p_name = player_points[pid]["name"]
                    if not p_name:
                        # Player was dropped before season end and ESPN has
                        # scrubbed them — check KEEPER_POINT_OVERRIDES for a
                        # matching (year, owner) entry to recover the name.
                        for (ov_year, ov_owner, ov_player) in KEEPER_POINT_OVERRIDES:
                            if (ov_year == year
                                    and self._title_case_owner(ov_owner) == owner):
                                p_name = ov_player
                                break
                    if not p_name:
                        p_name = "Unknown"
                    raw_keepers.append({
                        "owner":     owner,
                        "player":    p_name,
                        "roundKept": round_k,
                        "playerId":  pid,
                    })

            # ── 5. Enrich keepers with points + verdict ───────────────────
            enriched = []
            for k in raw_keepers:
                pid       = k["playerId"]
                norm_name = self._normalize_name(k["player"])

                # Resolve points from player_points
                p_info = None
                if pid and pid in player_points:
                    p_info = player_points[pid]
                elif not pid:
                    # name-only match (hardcoded 2018-2021 keepers not yet on roster)
                    resolved = pid_by_name.get(norm_name)
                    if resolved:
                        pid    = resolved
                        p_info = player_points.get(pid)

                points          = p_info["points"]          if p_info else None
                dropped         = p_info["droppedMidSeason"] if p_info else False
                last_active_wk  = p_info["lastActiveWeek"]  if p_info else None

                # Update player name from roster data if we had "Unknown"
                if p_info and p_info["name"] and (
                    not k["player"] or k["player"] == "Unknown"
                ):
                    k["player"] = p_info["name"]

                # Check manual override first (players ESPN has scrubbed)
                override_key = (year, k["owner"], k["player"])
                if override_key in KEEPER_POINT_OVERRIDES:
                    override_val = KEEPER_POINT_OVERRIDES[override_key]
                    points         = override_val[0]
                    dropped        = override_val[1]
                    last_active_wk = override_val[2] if dropped else None
                    print(f"    ⚡ Override applied: {k['player']} ({year}) "
                          f"= {points} pts"
                          f"{f' [dropped wk {last_active_wk}]' if dropped else ''}")
                # Zero-points fallback: targeted weekly sweep for dropped players.
                # Since we already did a full sweep, zeros here are genuine
                # absences — player wasn't on any roster any week (e.g. cut
                # pre-season or ESPN scrubbed them). Try one more targeted pass
                # in case they appear under a slightly different team context.
                elif (points is None or points == 0.0):
                    print(f"    ↩ Zero/missing — weekly fallback for "
                          f"{k['player']} ({year})...")
                    fallback, recovered_name = self._get_player_points_with_fallback(
                        year, player_points, pid, norm_name, reg_season_weeks
                    )
                    if fallback:
                        points         = fallback["points"]
                        dropped        = fallback["droppedMidSeason"]
                        last_active_wk = fallback["lastActiveWeek"]
                    if recovered_name and (
                        not k["player"] or k["player"] == "Unknown"
                    ):
                        k["player"] = recovered_name

                # Verdict
                round_kept    = k["roundKept"]
                round_avg     = benchmarks.get(round_kept)
                points_vs_avg = None
                pct_vs_avg    = None

                if points is not None and round_avg and round_avg > 0:
                    points_vs_avg = round(points - round_avg, 2)
                    pct_vs_avg    = round((points - round_avg) / round_avg, 4)
                    if pct_vs_avg >= VERDICT_THRESHOLD:
                        verdict = "STEAL"
                    elif pct_vs_avg <= -VERDICT_THRESHOLD:
                        verdict = "BUST"
                    else:
                        verdict = "AVERAGE"
                elif points is None:
                    verdict = "NO_DATA"
                else:
                    # points == 0.0 and no round_avg (shouldn't happen often)
                    verdict = "BUST" if round_avg else "NO_DATA"

                enriched.append({
                    "owner":            k["owner"],
                    "player":           k["player"],
                    "roundKept":        round_kept,
                    "pointsScored":     round(points, 2) if points is not None else None,
                    "roundAvgPoints":   round_avg,
                    "pointsVsAvg":      points_vs_avg,
                    "pointsVsAvgPct":   pct_vs_avg,
                    "verdict":          verdict,
                    "droppedMidSeason": dropped,
                    "lastActiveWeek":   last_active_wk,
                    "note":             KEEPER_NOTES.get((year, k["owner"], k["player"])),
                })

                verdict_icon = {
                    "STEAL": "🟢", "BUST": "🔴",
                    "AVERAGE": "🟡", "NO_DATA": "❓"
                }.get(verdict, "❓")
                pts_str  = f"{points:.1f}" if points is not None else "N/A"
                avg_str  = f"{round_avg:.1f}" if round_avg else "N/A"
                drop_str = f" [dropped wk {last_active_wk}]" if dropped else ""
                print(f"    {verdict_icon} {k['owner']:<20} {k['player']:<25} "
                      f"Rd {round_kept}  {pts_str} pts (avg {avg_str})"
                      f"  {verdict}{drop_str}")

            keepers_by_year[year] = enriched
            print(f"    → {len(enriched)} keepers for {year}")

        return keepers_by_year, benchmarks_by_year

    def _counter_ties_at_max(self, counter):
        """Given an owner -> count dict, return (owners, max_count) where
        owners is every owner tied for the max count, sorted alphabetically
        for stable output. Returns ([], 0) if counter is empty. Prevents
        superlatives like 'most weekly high scores' from silently dropping
        every owner but one when there's a tie at the top."""
        if not counter:
            return [], 0
        max_count = max(counter.values())
        owners = sorted(o for o, c in counter.items() if c == max_count)
        return owners, max_count

    def _compute_owner_streaks(self, owner_games):
        """For each owner, walk their games in chronological order and find
        their OWN best win streak and best loss streak (length plus detail:
        team, start/end year+week, whether it's still active as of their
        most recent game). Games only need 'won'/'lost' booleans and 'week';
        'year' and 'teamName' are optional and included in the detail when
        present. Returns (best_win_by_owner, best_loss_by_owner) dicts."""
        best_win = {}
        best_loss = {}

        for owner, games in owner_games.items():
            games = sorted(games, key=lambda g: (g.get('year', 0), g['week']))

            current_win = 0
            current_win_start = None
            current_loss = 0
            current_loss_start = None

            for i, game in enumerate(games):
                is_last = (i == len(games) - 1)

                if game['won']:
                    if current_win == 0:
                        current_win_start = game
                    current_win += 1
                    current_loss = 0

                    if owner not in best_win or current_win > best_win[owner]['length']:
                        best_win[owner] = {
                            'owner': owner,
                            'length': current_win,
                            'teamName': game.get('teamName'),
                            'startYear': current_win_start.get('year'),
                            'startWeek': current_win_start['week'],
                            'endYear': game.get('year'),
                            'endWeek': game['week'],
                            'isOngoing': is_last
                        }
                elif game['lost']:
                    if current_loss == 0:
                        current_loss_start = game
                    current_loss += 1
                    current_win = 0

                    if owner not in best_loss or current_loss > best_loss[owner]['length']:
                        best_loss[owner] = {
                            'owner': owner,
                            'length': current_loss,
                            'teamName': game.get('teamName'),
                            'startYear': current_loss_start.get('year'),
                            'startWeek': current_loss_start['week'],
                            'endYear': game.get('year'),
                            'endWeek': game['week'],
                            'isOngoing': is_last
                        }
                else:
                    current_win = 0
                    current_loss = 0

        return best_win, best_loss

    def _streak_ties_at_max(self, best_by_owner):
        """Given an owner -> streak-detail dict (each with a 'length' key),
        return (tied_details, max_length): every owner's detail dict tied
        for the max length, sorted by owner name. Returns ([], 0) if empty."""
        if not best_by_owner:
            return [], 0
        max_length = max(d['length'] for d in best_by_owner.values())
        tied = sorted(
            (d for d in best_by_owner.values() if d['length'] == max_length),
            key=lambda d: d['owner']
        )
        return tied, max_length

    def _compute_period_transaction_stats(self, executed, members, year, team_attribution_start_year):
        """Compute most-dropped/sloppy-seconds stats for a given list of EXECUTED
        transactions. Caller decides which weeks to include (e.g. all weeks for
        the full-season view, or scoring_period <= reg_season_count for a
        regular-season-only view) - this method itself is period-agnostic.
        """
        league_drop_counts = Counter()
        for t in executed:
            for item in t.items:
                if item.type == 'DROP':
                    league_drop_counts[item.player] += 1
        league_wide_top3 = [
            {'player': player, 'count': count}
            for player, count in league_drop_counts.most_common(3)
        ]

        if year < team_attribution_start_year:
            return {
                'league_wide_top3': league_wide_top3,
                'per_team_top3': None,
                'sloppy': None,
                'team_tally': {},
                'same_week_flagged': 0
            }

        team_drop_counts = defaultdict(Counter)
        for t in executed:
            if t.team is None:
                continue
            owner = self.get_owner_name_from_team(t.team, members)
            if not owner:
                continue
            for item in t.items:
                if item.type == 'DROP':
                    team_drop_counts[owner][item.player] += 1

        per_team_top3 = {
            owner: [{'player': player, 'count': count} for player, count in counts.most_common(3)]
            for owner, counts in team_drop_counts.items()
        }

        # Sort chronologically by week so "who added it next" is meaningful.
        # Transactions within the same week have no finer ordering available
        # from this data (scoring_period only resolves to the week).
        executed_sorted = sorted(executed, key=lambda t: t.scoring_period)

        player_add_sequence = defaultdict(list)  # player -> [(week, owner), ...]
        for t in executed_sorted:
            if t.team is None:
                continue
            owner = self.get_owner_name_from_team(t.team, members)
            if not owner:
                continue
            for item in t.items:
                if item.type == 'ADD':
                    player_add_sequence[item.player].append((t.scoring_period, owner))

        multi_team_players = []
        team_tally = Counter()
        same_week_flagged = 0

        for player, seq in player_add_sequence.items():
            distinct_owners = list(dict.fromkeys(owner for _, owner in seq))
            if len(distinct_owners) < 2:
                continue

            multi_team_players.append({
                'player': player,
                'teamCount': len(distinct_owners),
                'teams': distinct_owners
            })

            seen_owners = set()
            for week, owner in seq:
                if seen_owners and owner not in seen_owners:
                    prior_same_week = any(
                        wk == week and ow != owner
                        for wk, ow in seq if (wk, ow) != (week, owner)
                    )
                    if prior_same_week:
                        same_week_flagged += 1
                    else:
                        team_tally[owner] += 1
                seen_owners.add(owner)

        multi_team_players.sort(key=lambda x: x['teamCount'], reverse=True)

        return {
            'league_wide_top3': league_wide_top3,
            'per_team_top3': per_team_top3,
            'sloppy': {
                'players': multi_team_players,
                'teamTally': dict(team_tally),
                'sameWeekAddsFlagged': same_week_flagged
            },
            'team_tally': dict(team_tally),
            'same_week_flagged': same_week_flagged
        }

    def calculate_transaction_analysis(self):
        """Calculate most-dropped-player and 'sloppy seconds' stats from waiver/free-agent transactions.

        ESPN API constraints confirmed empirically for MMT (reference: espn-api
        source at https://github.com/cwendt94/espn-api - transactions()/Transaction/
        TransactionItem are not documented in detail, so behavior below was
        verified directly against this league rather than assumed):

        - league.transactions() returns NO data at all for 2013-2017 (not a
          documented library limit - just observed behavior for this league).
        - Only status == 'EXECUTED' transactions represent moves that actually
          took effect; PENDING/FAILED_*/CANCELED are waiver claims that never
          went through and must be excluded.
        - In 2018 ONLY, every WAIVER-type transaction has team=None (confirmed
          100% broken that season, 0% broken every other year 2019-2025).
          FREEAGENT-type transactions resolve team correctly even in 2018.
          This means 2018 can support league-wide "most dropped" (player name
          is present on every DROP item regardless of team resolution) but
          NOT per-team or sloppy-seconds stats, which require knowing which
          team/owner performed each move.
        - TransactionItem only exposes .type ('ADD'/'DROP') and .player
          (player name string) - no player ID, so matching is by name like
          the rest of this collector.
        - Transaction.scoring_period only resolves to the WEEK, not a precise
          timestamp, so two teams adding the same player in the same week
          cannot be reliably ordered - these are flagged as 'same-week adds'
          rather than arbitrarily attributed to one team.

        Produces TWO parallel views from the same fetched data (no extra API
        calls needed): the full-season view (all weeks, including playoffs -
        unchanged from before, still used by season-stats.html/teams.html/
        index.html), and a 'regularSeasonOnly' view filtered to
        scoring_period <= reg_season_count, for pages like regular-season.html
        that need genuinely regular-season-scoped stats rather than the whole
        season lumped together.
        """
        print(f"\n{'='*80}")
        print(" Calculating Transaction Analysis (Most Dropped / Sloppy Seconds)")
        print(f"{'='*80}")

        TRANSACTION_DATA_START_YEAR = 2018  # transactions() returns nothing before this
        TEAM_ATTRIBUTION_START_YEAR = 2019  # 2018 WAIVER moves have team=None

        league_wide_most_dropped = {}
        per_team_most_dropped = {}
        sloppy_seconds_by_year = {}
        all_time_team_tally = defaultdict(int)
        all_time_same_week_flagged = 0

        reg_league_wide_most_dropped = {}
        reg_per_team_most_dropped = {}
        reg_sloppy_seconds_by_year = {}
        reg_all_time_team_tally = defaultdict(int)
        reg_all_time_same_week_flagged = 0

        for season_data in self.all_seasons:
            year = season_data['year']
            league = season_data['league']

            if year < TRANSACTION_DATA_START_YEAR:
                continue

            print(f"  Processing {year} transactions...")

            members = {}
            if hasattr(league, 'members') and league.members:
                try:
                    if hasattr(league.members, 'items'):
                        members = league.members
                    else:
                        members = {m.id: m for m in league.members}
                except (AttributeError, TypeError):
                    members = {}

            reg_weeks = getattr(league.settings, 'reg_season_count', 14)
            total_weeks_to_try = reg_weeks + 4
            total_weeks_to_try = self._completed_weeks(league, total_weeks_to_try)

            all_transactions = []
            for week in range(1, total_weeks_to_try + 1):
                try:
                    week_transactions = league.transactions(
                        scoring_period=week,
                        types={"FREEAGENT", "WAIVER", "WAIVER_ERROR"}
                    )
                    all_transactions.extend(week_transactions)
                except Exception:
                    continue

            executed = [t for t in all_transactions if t.status == 'EXECUTED']
            reg_season_executed = [t for t in executed if t.scoring_period <= reg_weeks]

            # --- Full season (unchanged behavior - includes playoff weeks) ---
            full = self._compute_period_transaction_stats(
                executed, members, year, TEAM_ATTRIBUTION_START_YEAR
            )
            league_wide_most_dropped[year] = full['league_wide_top3']
            per_team_most_dropped[year] = full['per_team_top3']
            sloppy_seconds_by_year[year] = full['sloppy']
            for owner, cnt in full['team_tally'].items():
                all_time_team_tally[owner] += cnt
            all_time_same_week_flagged += full['same_week_flagged']

            # --- Regular season only (new - excludes playoff weeks) ---
            reg = self._compute_period_transaction_stats(
                reg_season_executed, members, year, TEAM_ATTRIBUTION_START_YEAR
            )
            reg_league_wide_most_dropped[year] = reg['league_wide_top3']
            reg_per_team_most_dropped[year] = reg['per_team_top3']
            reg_sloppy_seconds_by_year[year] = reg['sloppy']
            for owner, cnt in reg['team_tally'].items():
                reg_all_time_team_tally[owner] += cnt
            reg_all_time_same_week_flagged += reg['same_week_flagged']

            if year < TEAM_ATTRIBUTION_START_YEAR:
                print(f"    {year}: {len(executed)} executed transactions "
                      f"({len(reg_season_executed)} regular season only) - "
                      f"league-wide only (team attribution unavailable this season)")
            else:
                print(f"    {year}: {len(executed)} executed transactions "
                      f"({len(reg_season_executed)} regular season only), "
                      f"{len(full['sloppy']['players'])} players with 2+ teams full-season "
                      f"({len(reg['sloppy']['players'])} regular-season-only)")

        result = {
            'leagueWideMostDropped': league_wide_most_dropped,
            'perTeamMostDropped': per_team_most_dropped,
            'sloppySeconds': {
                'byYear': sloppy_seconds_by_year,
                'allTimeTeamTally': dict(all_time_team_tally),
                'allTimeSameWeekAddsFlagged': all_time_same_week_flagged
            },
            'regularSeasonOnly': {
                'leagueWideMostDropped': reg_league_wide_most_dropped,
                'perTeamMostDropped': reg_per_team_most_dropped,
                'sloppySeconds': {
                    'byYear': reg_sloppy_seconds_by_year,
                    'allTimeTeamTally': dict(reg_all_time_team_tally),
                    'allTimeSameWeekAddsFlagged': reg_all_time_same_week_flagged
                }
            },
            'metadata': {
                'transactionDataYears': f'{TRANSACTION_DATA_START_YEAR}-{self.end_year}',
                'teamAttributionYears': f'{TEAM_ATTRIBUTION_START_YEAR}-{self.end_year}',
                'notes': (
                    f'{self.start_year}-{TRANSACTION_DATA_START_YEAR - 1}: no transaction data '
                    f'available via ESPN API (confirmed empirically, all weeks error). '
                    f'{TRANSACTION_DATA_START_YEAR}: league-wide most-dropped only - '
                    f'per-team and sloppy-seconds stats are null this season because WAIVER-type '
                    f'transactions have no team attribution (100% of that season\'s waiver moves, '
                    f'confirmed 0% broken in every other year 2019-2025). '
                    f'"Same-week adds" are pickups that cannot be ordered against a same-week drop '
                    f'from another team (scoring_period only resolves to the week) - these are '
                    f'excluded from team-level tallies rather than arbitrarily attributed. '
                    f'Top-level keys cover the full season including playoff weeks; '
                    f'"regularSeasonOnly" mirrors the same structure filtered to '
                    f'scoring_period <= that season\'s reg_season_count.'
                )
            }
        }

        print(f"  ✓ Transaction analysis complete")
        return result

    def save_output(self, data, filename):
        """Save to JSON"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"  ✓ Saved to {filepath}")
    
    def run(self, skip_bench=False):
        """Main execution"""
        print(f"\n{'='*80}")
        print(" ESPN Fantasy Football Data Collector V2")
        print(" Using espn-api library")
        print(f"{'='*80}")
        print(f"League ID: {self.league_id}")
        print(f"Year Range: {self.start_year}-{self.end_year}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if skip_bench:
            print(f"⚠️  SKIPPING BENCH POINTS CALCULATION")
        
        if not self.fetch_all_seasons():
            print("\n✗ No data fetched. Exiting.")
            return
        
        print(f"\n{'='*80}")
        print(" Tracking Team Names")
        print(f"{'='*80}")
        team_names = self.get_most_recent_team_names()
        print(f"  ✓ Tracked {len(team_names)} teams")
        
        all_matchups = self.process_all_matchups(team_names)
        team_stats = self.calculate_team_stats(all_matchups, team_names)
        team_stats = self.calculate_player_loyalty_stats(team_stats)
        h2h_stats = self.calculate_head_to_head_stats(all_matchups, team_stats)
        superlatives = self.calculate_superlatives(all_matchups)
        roster_analysis = self.analyze_rosters_and_trades()
        two_week_analysis = self.analyze_two_week_playoff_comebacks(all_matchups)
        keepers_by_year, benchmarks_by_year = self.fetch_keeper_data_by_year()
        season_stats = self.calculate_season_stats(
            all_matchups,
            skip_bench=skip_bench,
            keepers_by_year=keepers_by_year,
            benchmarks_by_year=benchmarks_by_year,
        )
        transaction_analysis = self.calculate_transaction_analysis()
        
        print(f"\n{'='*80}")
        print(" Saving Output Files")
        print(f"{'='*80}")
        
        self.save_output(all_matchups, 'matchups.json')
        self.save_output(team_stats, 'team_stats.json')
        self.save_output(h2h_stats, 'head_to_head.json')
        self.save_output(superlatives, 'superlatives.json')
        self.save_output(season_stats, 'season_stats.json')
        self.save_output(roster_analysis, 'roster_analysis.json')
        self.save_output(two_week_analysis, 'two_week_playoff_analysis.json')
        self.save_output(transaction_analysis, 'transaction_analysis.json')
        
        metadata = {
            'leagueId': self.league_id,
            'inceptionYear': self.start_year,
            'currentYear': self.end_year,
            'totalSeasons': len(self.all_seasons),
            'totalMatchups': len(all_matchups),
            'totalTeams': len(team_stats),
            'lastUpdated': datetime.now().isoformat()
        }
        self.save_output(metadata, 'metadata.json')
        
        print(f"\n{'='*80}")
        print(" Complete!")
        print(f"{'='*80}")
        print(f"\nTotal matchups: {len(all_matchups)}")
        print(f"Total teams: {len(team_stats)}")
        print(f"Seasons: {self.start_year}-{self.end_year}")

def main():
    parser = argparse.ArgumentParser(description='ESPN Fantasy Football Data Collector')
    parser.add_argument('--skip-bench', action='store_true', 
                        help='Skip bench points calculation (faster for testing)')
    args = parser.parse_args()
    
    collector = ESPNDataCollectorV2(LEAGUE_ID, START_YEAR, END_YEAR, SWID, ESPN_S2)
    collector.run(skip_bench=args.skip_bench)

if __name__ == "__main__":
    main()