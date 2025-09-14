import re
import email
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class BetEmailParser:
    """Parse betting confirmation emails from various sportsbooks"""
    
    def __init__(self):
        self.sportsbook_patterns = {
            'fanduel': {
                'subject_pattern': r'FanDuel.*bet.*confirmation|Your FanDuel bet',
                'bet_patterns': {
                    'game': r'(?:vs\.?|@)\s*([A-Za-z\s]+(?:vs\.?|@)\s*[A-Za-z\s]+)',
                    'bet_type': r'(Spread|Moneyline|Over|Under|Total|Parlay)',
                    'odds': r'([+-]\d+)',
                    'stake': r'\$(\d+\.?\d*)',
                    'potential_payout': r'Win:\s*\$(\d+\.?\d*)|Payout:\s*\$(\d+\.?\d*)'
                }
            },
            'draftkings': {
                'subject_pattern': r'DraftKings.*bet.*confirmation|Your DraftKings bet',
                'bet_patterns': {
                    'game': r'(?:vs\.?|@)\s*([A-Za-z\s]+(?:vs\.?|@)\s*[A-Za-z\s]+)',
                    'bet_type': r'(Spread|Moneyline|Over|Under|Total|Parlay)',
                    'odds': r'([+-]\d+)',
                    'stake': r'\$(\d+\.?\d*)',
                    'potential_payout': r'Win:\s*\$(\d+\.?\d*)|Payout:\s*\$(\d+\.?\d*)'
                }
            },
            'caesars': {
                'subject_pattern': r'Caesars.*bet.*confirmation|Your Caesars bet',
                'bet_patterns': {
                    'game': r'(?:vs\.?|@)\s*([A-Za-z\s]+(?:vs\.?|@)\s*[A-Za-z\s]+)',
                    'bet_type': r'(Spread|Moneyline|Over|Under|Total|Parlay)',
                    'odds': r'([+-]\d+)',
                    'stake': r'\$(\d+\.?\d*)',
                    'potential_payout': r'Win:\s*\$(\d+\.?\d*)|Payout:\s*\$(\d+\.?\d*)'
                }
            }
        }
    
    def parse_email(self, email_content, email_subject=""):
        """Parse a betting confirmation email and extract bet details"""
        
        # Determine sportsbook
        sportsbook = self._identify_sportsbook(email_subject, email_content)
        if not sportsbook:
            return None
        
        patterns = self.sportsbook_patterns[sportsbook]['bet_patterns']
        
        # Extract bet details
        bet_data = {
            'sportsbook': sportsbook,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'sport': self._extract_sport(email_content),
            'bet_type': self._extract_pattern(email_content, patterns.get('bet_type', '')),
            'game_description': self._extract_pattern(email_content, patterns.get('game', '')),
            'odds': self._extract_pattern(email_content, patterns.get('odds', '')),
            'stake': self._extract_pattern(email_content, patterns.get('stake', '')),
            'potential_payout': self._extract_pattern(email_content, patterns.get('potential_payout', ''))
        }
        
        # Clean and validate data
        bet_data = self._clean_bet_data(bet_data)
        
        return bet_data if self._validate_bet_data(bet_data) else None
    
    def _identify_sportsbook(self, subject, content):
        """Identify which sportsbook sent the email"""
        text = (subject + " " + content).lower()
        
        for sportsbook, config in self.sportsbook_patterns.items():
            if re.search(config['subject_pattern'].lower(), text):
                return sportsbook
        
        # Fallback - check for sportsbook names in content
        if 'fanduel' in text:
            return 'fanduel'
        elif 'draftkings' in text:
            return 'draftkings'
        elif 'caesars' in text:
            return 'caesars'
        
        return None
    
    def _extract_pattern(self, text, pattern):
        """Extract data using regex pattern"""
        if not pattern:
            return ""
        
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Return first non-None group
            for group in match.groups():
                if group:
                    return group.strip()
        return ""
    
    def _extract_sport(self, content):
        """Extract sport from email content"""
        sports_keywords = {
            'NFL': ['nfl', 'football', 'patriots', 'chiefs', 'cowboys'],
            'NBA': ['nba', 'basketball', 'lakers', 'warriors', 'celtics'],
            'MLB': ['mlb', 'baseball', 'yankees', 'dodgers', 'red sox'],
            'NHL': ['nhl', 'hockey', 'rangers', 'bruins', 'penguins'],
            'Soccer': ['soccer', 'mls', 'premier league', 'champions league'],
            'Tennis': ['tennis', 'atp', 'wta', 'wimbledon', 'us open'],
            'Golf': ['golf', 'pga', 'masters', 'open championship']
        }
        
        content_lower = content.lower()
        for sport, keywords in sports_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return sport
        
        return "Other"
    
    def _clean_bet_data(self, bet_data):
        """Clean and format extracted bet data"""
        # Clean odds
        if bet_data['odds']:
            bet_data['odds'] = re.sub(r'[^\d+-]', '', bet_data['odds'])
        
        # Clean monetary values
        for field in ['stake', 'potential_payout']:
            if bet_data[field]:
                bet_data[field] = re.sub(r'[^\d.]', '', bet_data[field])
        
        # Clean game description
        if bet_data['game_description']:
            bet_data['game_description'] = re.sub(r'\s+', ' ', bet_data['game_description']).strip()
        
        return bet_data
    
    def _validate_bet_data(self, bet_data):
        """Validate that essential bet data is present"""
        required_fields = ['stake', 'odds']
        return all(bet_data.get(field) for field in required_fields)

# Example usage and test data
def test_parser():
    parser = BetEmailParser()
    
    # Sample FanDuel email content
    sample_email = """
    Your FanDuel bet confirmation
    
    Game: Chiefs vs Bills
    Bet: Chiefs -3.5 (Spread)
    Odds: -110
    Stake: $25.00
    Potential Win: $22.73
    Total Payout: $47.73
    
    Good luck!
    """
    
    result = parser.parse_email(sample_email, "FanDuel Bet Confirmation")
    print("Parsed bet data:", result)

if __name__ == "__main__":
    test_parser()
