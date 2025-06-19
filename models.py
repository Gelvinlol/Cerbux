from datetime import datetime, date
from app import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # Διοικητής, Υπασπιστήριο, ΑΥΔΜ, ΓΡΑΦΙΟ ΑΡΧΗΛΟΧΕΙΑ
    full_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_commander(self):
        return self.role == "Διοικητής"
    
    def can_view_logs(self):
        return self.role == "Διοικητής"
    
    def __repr__(self):
        return f'<User {self.username}>'

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))  # soldier, duty, schedule, etc.
    target_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('activity_logs', lazy=True))
    
    def __repr__(self):
        return f'<ActivityLog {self.action} by {self.user.username}>'

class Soldier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    military_id = db.Column(db.String(20), unique=True, nullable=False)
    enlistment_date = db.Column(db.Date, nullable=False)
    specialty = db.Column(db.String(100))
    status = db.Column(db.String(50), default='Active')  # Active, On Leave
    exemption_no_duty = db.Column(db.Boolean, default=False)  # Άνευ υπηρεσίας
    exemption_no_shaving = db.Column(db.Boolean, default=False)  # Άνευ ξυρίσματος
    exemption_no_boots = db.Column(db.Boolean, default=False)  # Άνευ αρβυλών
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    duty_assignments = db.relationship('DutyAssignment', backref='soldier', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Soldier {self.name}>'
    
    def is_available_for_duty(self):
        """Check if soldier is available for duty assignment"""
        return self.status == 'Active' and not self.exemption_no_duty
    
    def get_duty_count_last_days(self, days=7):
        """Get number of duties in the last N days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return DutyAssignment.query.filter(
            DutyAssignment.soldier_id == self.id,
            DutyAssignment.duty_date >= cutoff_date
        ).count()

class DutyType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    team_size = db.Column(db.Integer, default=1)
    shifts_per_day = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    duty_assignments = db.relationship('DutyAssignment', backref='duty_type', lazy=True)
    time_slots = db.relationship('DutyTimeSlot', backref='duty_type', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<DutyType {self.name}>'

class DutyTimeSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    duty_type_id = db.Column(db.Integer, db.ForeignKey('duty_type.id'), nullable=False)
    shift_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3 for different shifts
    start_time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)    # Format: "HH:MM"
    
    def __repr__(self):
        return f'<DutyTimeSlot {self.duty_type.name} Shift {self.shift_number}>'

class DutyAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    soldier_id = db.Column(db.Integer, db.ForeignKey('soldier.id'), nullable=False)
    duty_type_id = db.Column(db.Integer, db.ForeignKey('duty_type.id'), nullable=False)
    duty_date = db.Column(db.Date, nullable=False)
    shift_number = db.Column(db.Integer, default=1)
    position_in_team = db.Column(db.Integer, default=1)  # For team-based duties
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DutyAssignment {self.soldier.name} - {self.duty_type.name}>'
    
    def get_time_slot(self):
        """Get the time slot for this duty assignment"""
        return DutyTimeSlot.query.filter_by(
            duty_type_id=self.duty_type_id,
            shift_number=self.shift_number
        ).first()

class DutySchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schedule_date = db.Column(db.Date, nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    is_finalized = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<DutySchedule {self.schedule_date}>'
