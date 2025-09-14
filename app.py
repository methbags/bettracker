from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from datetime import datetime, timedelta
import os
from sqlalchemy import func, extract
from werkzeug.utils import secure_filename
from email_parser import BetEmailParser
from csv_importer import BetCSVImporter
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bet_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', 'your-google-client-secret')
app.config['APPLE_CLIENT_ID'] = os.environ.get('APPLE_CLIENT_ID', 'your-apple-client-id')
app.config['APPLE_CLIENT_SECRET'] = os.environ.get('APPLE_CLIENT_SECRET', 'your-apple-client-secret')

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize OAuth
oauth = OAuth(app)

# Configure OAuth providers only if credentials are available
google = None
apple = None

# Configure Google OAuth if credentials are provided
if app.config.get('GOOGLE_CLIENT_ID') and app.config.get('GOOGLE_CLIENT_SECRET'):
    google = oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

# Configure Apple OAuth if credentials are provided
if app.config.get('APPLE_CLIENT_ID') and app.config.get('APPLE_CLIENT_SECRET'):
    apple = oauth.register(
        name='apple',
        client_id=app.config['APPLE_CLIENT_ID'],
        client_secret=app.config['APPLE_CLIENT_SECRET'],
        authorize_url='https://appleid.apple.com/auth/authorize',
        access_token_url='https://appleid.apple.com/auth/token',
        client_kwargs={'scope': 'name email'},
    )

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    apple_id = db.Column(db.String(100), unique=True, nullable=True)
    
    # Relationships
    bets = db.relationship('Bet', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Make config available in templates
@app.context_processor
def inject_config():
    return {
        'oauth_available': {
            'google': google is not None,
            'apple': apple is not None
        }
    }

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bet_type = db.Column(db.String(50), nullable=False)  # spread, moneyline, over/under, parlay, etc.
    sport = db.Column(db.String(50), nullable=False)
    game_description = db.Column(db.String(200), nullable=False)
    bet_description = db.Column(db.String(200), nullable=False)
    odds = db.Column(db.String(20), nullable=False)
    stake = db.Column(db.Float, nullable=False)
    potential_payout = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, won, lost, pushed
    actual_payout = db.Column(db.Float, default=0.0)
    week_number = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Bet {self.id}: {self.bet_description}>'

    @property
    def profit_loss(self):
        if self.status == 'won':
            return self.actual_payout - self.stake
        elif self.status == 'lost':
            return -self.stake
        elif self.status == 'pushed':
            return 0.0
        else:
            return 0.0  # pending

# Forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

def get_week_number(date):
    """Get week number for a given date (1-52)"""
    return date.isocalendar()[1]

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard')
            return redirect(next_page)
        flash('Invalid email or password', 'error')
    return render_template('auth/login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('auth/register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# OAuth Routes
@app.route('/auth/<provider>')
def oauth_login(provider):
    if provider == 'google':
        if not google:
            flash('Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.', 'error')
            return redirect(url_for('login'))
        redirect_uri = url_for('oauth_callback', provider='google', _external=True)
        return google.authorize_redirect(redirect_uri)
    elif provider == 'apple':
        if not apple:
            flash('Apple OAuth is not configured. Please set APPLE_CLIENT_ID and APPLE_CLIENT_SECRET environment variables.', 'error')
            return redirect(url_for('login'))
        redirect_uri = url_for('oauth_callback', provider='apple', _external=True)
        return apple.authorize_redirect(redirect_uri)
    else:
        flash('Invalid OAuth provider', 'error')
        return redirect(url_for('login'))

@app.route('/callback/<provider>')
def oauth_callback(provider):
    try:
        if provider == 'google':
            token = google.authorize_access_token()
            user_info = token.get('userinfo')
            if user_info:
                user = User.query.filter_by(google_id=user_info['sub']).first()
                if not user:
                    # Check if user exists with same email
                    user = User.query.filter_by(email=user_info['email']).first()
                    if user:
                        user.google_id = user_info['sub']
                    else:
                        # Create new user
                        user = User(
                            username=user_info['email'].split('@')[0],
                            email=user_info['email'],
                            google_id=user_info['sub']
                        )
                        db.session.add(user)
                    db.session.commit()
                
                login_user(user, remember=True)
                return redirect(url_for('dashboard'))
        
        elif provider == 'apple':
            token = apple.authorize_access_token()
            # Apple OAuth implementation would go here
            # Note: Apple OAuth requires more complex setup
            flash('Apple Sign-In coming soon!', 'info')
            return redirect(url_for('login'))
        
    except Exception as e:
        flash(f'Authentication failed: {str(e)}', 'error')
    
    return redirect(url_for('login'))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('auth/welcome.html')

@app.route('/add_bet', methods=['GET', 'POST'])
@login_required
def add_bet():
    if request.method == 'POST':
        data = request.get_json()
        
        bet_date = datetime.strptime(data['date'], '%Y-%m-%d')
        week_num = get_week_number(bet_date)
        
        bet = Bet(
            date=bet_date,
            bet_type=data['bet_type'],
            sport=data['sport'],
            game_description=data['game_description'],
            bet_description=data['bet_description'],
            odds=data['odds'],
            stake=float(data['stake']),
            potential_payout=float(data['potential_payout']),
            status=data.get('status', 'pending'),
            actual_payout=float(data.get('actual_payout', 0)),
            week_number=week_num,
            year=bet_date.year,
            user_id=current_user.id
        )
        
        db.session.add(bet)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Bet added successfully!'})
    
    return render_template('add_bet.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get current week stats
    current_date = datetime.now()
    current_week = get_week_number(current_date)
    current_year = current_date.year
    
    # Weekly stats - filter by current user
    weekly_bets = Bet.query.filter_by(week_number=current_week, year=current_year, user_id=current_user.id).all()
    weekly_stats = calculate_stats(weekly_bets)
    
    # Overall stats - filter by current user
    all_bets = Bet.query.filter_by(user_id=current_user.id).all()
    overall_stats = calculate_stats(all_bets)
    
    # Bet type breakdown
    bet_type_stats = {}
    for bet_type in ['spread', 'moneyline', 'over/under', 'parlay', 'prop']:
        type_bets = [bet for bet in all_bets if bet.bet_type.lower() == bet_type]
        if type_bets:
            bet_type_stats[bet_type] = calculate_stats(type_bets)
    
    # Recent bets - filter by current user
    recent_bets = Bet.query.filter_by(user_id=current_user.id).order_by(Bet.date.desc()).limit(10).all()
    
    return render_template('dashboard.html', 
                         weekly_stats=weekly_stats,
                         overall_stats=overall_stats,
                         bet_type_stats=bet_type_stats,
                         recent_bets=recent_bets,
                         current_week=current_week)

@app.route('/weekly_history')
@login_required
def weekly_history():
    # Get all weeks with bets - filter by current user
    weeks_data = db.session.query(
        Bet.year, 
        Bet.week_number,
        func.count(Bet.id).label('total_bets'),
        func.sum(Bet.stake).label('total_staked'),
        func.sum(Bet.actual_payout).label('total_payout')
    ).filter_by(user_id=current_user.id).group_by(Bet.year, Bet.week_number).order_by(Bet.year.desc(), Bet.week_number.desc()).all()
    
    weekly_history = []
    for week_data in weeks_data:
        week_bets = Bet.query.filter_by(year=week_data.year, week_number=week_data.week_number, user_id=current_user.id).all()
        stats = calculate_stats(week_bets)
        stats['year'] = week_data.year
        stats['week_number'] = week_data.week_number
        weekly_history.append(stats)
    
    return render_template('weekly_history.html', weekly_history=weekly_history)

@app.route('/update_bet/<int:bet_id>', methods=['POST'])
@login_required
def update_bet(bet_id):
    bet = Bet.query.filter_by(id=bet_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    bet.status = data['status']
    if data['status'] == 'won':
        bet.actual_payout = float(data.get('actual_payout', bet.potential_payout))
    elif data['status'] == 'lost':
        bet.actual_payout = 0.0
    elif data['status'] == 'pushed':
        bet.actual_payout = bet.stake
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Bet updated successfully!'})

@app.route('/import_data', methods=['GET', 'POST'])
@login_required
def import_data():
    if request.method == 'POST':
        import_type = request.form.get('import_type')
        
        if import_type == 'csv':
            return handle_csv_import()
        elif import_type == 'email':
            return handle_email_import()
    
    return render_template('import_data.html')

def handle_csv_import():
    """Handle CSV file import"""
    if 'csv_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('import_data'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('import_data'))
    
    if file and file.filename.lower().endswith('.csv'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Import CSV data
        importer = BetCSVImporter()
        result = importer.import_from_csv(filepath)
        
        if result['success']:
            # Add bets to database
            imported_count = 0
            for bet_data in result['bets']:
                bet_date = datetime.strptime(bet_data['date'], '%Y-%m-%d')
                week_num = get_week_number(bet_date)
                
                bet = Bet(
                    date=bet_date,
                    bet_type=bet_data['bet_type'],
                    sport=bet_data['sport'],
                    game_description=bet_data['game_description'],
                    bet_description=bet_data['bet_description'],
                    odds=bet_data['odds'],
                    stake=bet_data['stake'],
                    potential_payout=bet_data['potential_payout'],
                    status=bet_data['status'],
                    actual_payout=bet_data['actual_payout'],
                    week_number=week_num,
                    year=bet_date.year,
                    user_id=current_user.id
                )
                
                db.session.add(bet)
                imported_count += 1
            
            db.session.commit()
            flash(f'Successfully imported {imported_count} bets', 'success')
            
            if result['skipped']:
                flash(f'Skipped {len(result["skipped"])} rows due to errors', 'warning')
        else:
            flash(f'Import failed: {result["error"]}', 'error')
        
        # Clean up uploaded file
        os.remove(filepath)
    else:
        flash('Please upload a valid CSV file', 'error')
    
    return redirect(url_for('import_data'))

def handle_email_import():
    """Handle email text import"""
    email_content = request.form.get('email_content', '')
    email_subject = request.form.get('email_subject', '')
    
    if not email_content:
        flash('Please provide email content', 'error')
        return redirect(url_for('import_data'))
    
    parser = BetEmailParser()
    bet_data = parser.parse_email(email_content, email_subject)
    
    if bet_data:
        bet_date = datetime.strptime(bet_data['date'], '%Y-%m-%d')
        week_num = get_week_number(bet_date)
        
        bet = Bet(
            date=bet_date,
            bet_type=bet_data['bet_type'] or 'unknown',
            sport=bet_data['sport'] or 'Other',
            game_description=bet_data['game_description'] or 'Unknown Game',
            bet_description=bet_data.get('bet_description', bet_data['game_description']),
            odds=bet_data['odds'] or '+100',
            stake=float(bet_data['stake']) if bet_data['stake'] else 0.0,
            potential_payout=float(bet_data['potential_payout']) if bet_data['potential_payout'] else 0.0,
            status='pending',
            actual_payout=0.0,
            week_number=week_num,
            year=bet_date.year,
            user_id=current_user.id
        )
        
        db.session.add(bet)
        db.session.commit()
        flash('Successfully imported bet from email', 'success')
    else:
        flash('Could not parse bet information from email', 'error')
    
    return redirect(url_for('import_data'))

@app.route('/download_template')
@login_required
def download_template():
    """Generate and download CSV template"""
    importer = BetCSVImporter()
    template_path = os.path.join(app.config['UPLOAD_FOLDER'], 'bet_import_template.csv')
    importer.generate_template_csv(template_path)
    
    return send_file(template_path, as_attachment=True, download_name='bet_import_template.csv')

def calculate_stats(bets):
    """Calculate statistics for a list of bets"""
    if not bets:
        return {
            'total_bets': 0,
            'wins': 0,
            'losses': 0,
            'pushes': 0,
            'pending': 0,
            'win_rate': 0,
            'total_staked': 0,
            'total_payout': 0,
            'profit_loss': 0,
            'roi': 0
        }
    
    total_bets = len(bets)
    wins = len([bet for bet in bets if bet.status == 'won'])
    losses = len([bet for bet in bets if bet.status == 'lost'])
    pushes = len([bet for bet in bets if bet.status == 'pushed'])
    pending = len([bet for bet in bets if bet.status == 'pending'])
    
    win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
    
    total_staked = sum(bet.stake for bet in bets)
    total_payout = sum(bet.actual_payout for bet in bets)
    profit_loss = total_payout - total_staked
    roi = (profit_loss / total_staked) * 100 if total_staked > 0 else 0
    
    return {
        'total_bets': total_bets,
        'wins': wins,
        'losses': losses,
        'pushes': pushes,
        'pending': pending,
        'win_rate': round(win_rate, 2),
        'total_staked': round(total_staked, 2),
        'total_payout': round(total_payout, 2),
        'profit_loss': round(profit_loss, 2),
        'roi': round(roi, 2)
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
