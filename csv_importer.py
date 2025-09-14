import csv
from datetime import datetime
import re

class BetCSVImporter:
    """Import betting data from CSV files"""
    
    def __init__(self):
        self.required_columns = ['date', 'bet_type', 'sport', 'game_description', 'bet_description', 'odds', 'stake', 'potential_payout']
        self.optional_columns = ['status', 'actual_payout']
        
    def import_from_csv(self, file_path):
        """Import bets from a CSV file"""
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                return self._process_csv_reader(reader)
        except Exception as e:
            return {'success': False, 'error': str(e), 'bets': []}
    
    def _process_csv_reader(self, reader):
        """Process CSV reader and convert to bet records"""
        results = {'success': True, 'error': None, 'bets': [], 'skipped': []}
        
        # Get fieldnames from reader
        fieldnames = reader.fieldnames or []
        
        # Check for required columns
        missing_columns = [col for col in self.required_columns if col not in fieldnames]
        if missing_columns:
            return {
                'success': False, 
                'error': f'Missing required columns: {", ".join(missing_columns)}',
                'bets': []
            }
        
        for index, row in enumerate(reader, start=1):
            try:
                bet_data = self._process_row(row)
                if bet_data:
                    results['bets'].append(bet_data)
                else:
                    results['skipped'].append(f'Row {index}: Invalid data')
            except Exception as e:
                results['skipped'].append(f'Row {index}: {str(e)}')
        
        return results
    
    def _process_row(self, row):
        """Process a single row into bet data"""
        try:
            # Parse date
            date_str = str(row['date'])
            try:
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
            except:
                try:
                    parsed_date = datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                except:
                    parsed_date = datetime.now().strftime('%Y-%m-%d')
            
            # Clean and validate numeric fields
            stake = self._clean_numeric(row['stake'])
            potential_payout = self._clean_numeric(row['potential_payout'])
            
            if not stake or not potential_payout:
                return None
            
            bet_data = {
                'date': parsed_date,
                'bet_type': self._clean_text(row['bet_type']),
                'sport': self._clean_text(row['sport']),
                'game_description': self._clean_text(row['game_description']),
                'bet_description': self._clean_text(row['bet_description']),
                'odds': self._clean_text(row['odds']),
                'stake': float(stake),
                'potential_payout': float(potential_payout),
                'status': self._clean_text(row.get('status', 'pending')),
                'actual_payout': float(self._clean_numeric(row.get('actual_payout', 0)) or 0)
            }
            
            return bet_data
            
        except Exception as e:
            print(f"Error processing row: {e}")
            return None
    
    def _clean_numeric(self, value):
        """Clean and extract numeric value"""
        if value is None or value == '' or str(value).lower() == 'nan':
            return None
        
        # Convert to string and remove currency symbols and commas
        clean_value = re.sub(r'[$,\s]', '', str(value))
        
        try:
            return float(clean_value)
        except ValueError:
            return None
    
    def _clean_text(self, value):
        """Clean text value"""
        if value is None or str(value).lower() == 'nan':
            return ""
        return str(value).strip()
    
    def generate_template_csv(self, file_path):
        """Generate a template CSV file for users to fill out"""
        template_rows = [
            {
                'date': '2024-01-15',
                'bet_type': 'spread',
                'sport': 'NFL',
                'game_description': 'Chiefs vs Bills',
                'bet_description': 'Chiefs -3.5',
                'odds': '-110',
                'stake': '25.00',
                'potential_payout': '47.73',
                'status': 'won',
                'actual_payout': '47.73'
            },
            {
                'date': '2024-01-16',
                'bet_type': 'moneyline',
                'sport': 'NBA',
                'game_description': 'Lakers vs Warriors',
                'bet_description': 'Lakers ML',
                'odds': '+150',
                'stake': '50.00',
                'potential_payout': '125.00',
                'status': 'pending',
                'actual_payout': '0.00'
            }
        ]
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = self.required_columns + self.optional_columns
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(template_rows)
        
        return file_path

# Example usage
def test_importer():
    importer = BetCSVImporter()
    
    # Generate template
    template_path = 'bet_template.csv'
    importer.generate_template_csv(template_path)
    print(f"Template generated: {template_path}")
    
    # Test import
    result = importer.import_from_csv(template_path)
    print("Import result:", result)

if __name__ == "__main__":
    test_importer()
