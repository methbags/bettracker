# FanDuel Bet Tracker

A comprehensive web application for tracking your FanDuel betting performance, analyzing your success rates, and managing your bankroll effectively.

## Features

- **Weekly Tracking**: Monitor your betting performance week by week
- **Bet Type Analysis**: Track success rates for different bet types (spread, moneyline, over/under, parlay, props)
- **Profit/Loss Calculation**: Automatic calculation of your profit/loss and ROI
- **Interactive Dashboard**: Beautiful, modern web interface with real-time statistics
- **Bet Management**: Add, update, and track the status of your bets
- **Historical Analysis**: Review your betting history with detailed weekly breakdowns

## Installation

1. Make sure you have Python 3.7+ installed
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the application:
   ```
   python app.py
   ```

2. Open your web browser and navigate to `http://localhost:5000`

3. Start adding your bets using the "Add New Bet" feature

4. Update bet outcomes as games conclude

5. Monitor your performance on the dashboard

## Bet Types Supported

- **Point Spread**: Traditional point spread bets
- **Moneyline**: Straight win/loss bets
- **Over/Under**: Total points/goals betting
- **Parlay**: Multiple bet combinations
- **Prop Bets**: Player and game proposition bets
- **Futures**: Long-term outcome bets
- **Live Bets**: In-game betting

## Dashboard Features

### Current Week Performance
- Total bets placed
- Win rate percentage
- Weekly profit/loss
- Return on investment (ROI)

### Overall Statistics
- All-time betting record
- Total money wagered
- Total profit/loss
- Overall ROI

### Bet Type Breakdown
- Performance analysis by bet type
- Success rates for each category
- Profit/loss by betting strategy

## Database

The application uses SQLite for data storage. The database file (`bet_tracker.db`) will be created automatically when you first run the application.

## Security Note

This application is designed for personal use and tracks your betting data locally. No data is shared with external services.

## Future Enhancements

- Import betting data from CSV files
- Advanced analytics and charts
- Bankroll management recommendations
- Mobile-responsive design improvements
- Export functionality for tax purposes

## Support

If you encounter any issues or have suggestions for improvements, please create an issue in the project repository.
