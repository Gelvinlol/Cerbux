from flask import render_template, request, redirect, url_for, flash, make_response, session
from datetime import datetime, date, timedelta
from app import app, db
from models import Soldier, DutyType, DutyAssignment, DutyTimeSlot, DutySchedule, User, ActivityLog
from simple_scheduler import SimpleScheduler
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import logging

def log_activity(action, target_type=None, target_id=None, description=None):
    """Log user activity"""
    if current_user.is_authenticated:
        log = ActivityLog(
            user_id=current_user.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            description=description,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            log_activity('login', description=f'User {username} logged in')
            
            next_page = request.args.get('next')
            flash(f'Καλώς ήρθατε, {user.full_name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Λανθασμένα στοιχεία σύνδεσης.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity('logout', description=f'User {current_user.username} logged out')
    logout_user()
    flash('Αποσυνδεθήκατε με επιτυχία.', 'info')
    return redirect(url_for('login'))

@app.route('/logs')
@login_required
def view_logs():
    if not current_user.can_view_logs():
        flash('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.', 'error')
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('logs.html', logs=logs)

@app.route('/')
@login_required
def index():
    # Get overview statistics
    total_soldiers = Soldier.query.count()
    active_soldiers = Soldier.query.filter_by(status='Active').count()
    soldiers_on_leave = Soldier.query.filter_by(status='On Leave').count()
    total_duty_types = DutyType.query.filter_by(is_active=True).count()
    
    # Get today's duties
    today = date.today()
    today_duties = db.session.query(DutyAssignment, Soldier, DutyType).join(
        Soldier, DutyAssignment.soldier_id == Soldier.id
    ).join(
        DutyType, DutyAssignment.duty_type_id == DutyType.id
    ).filter(
        DutyAssignment.duty_date == today
    ).order_by(DutyType.name, DutyAssignment.shift_number).all()
    
    stats = {
        'total_soldiers': total_soldiers,
        'active_soldiers': active_soldiers,
        'soldiers_on_leave': soldiers_on_leave,
        'total_duty_types': total_duty_types
    }
    
    return render_template('index.html', stats=stats, today_duties=today_duties, today=today)

@app.route('/soldiers')
@login_required
def soldiers():
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = Soldier.query
    
    if search:
        query = query.filter(
            db.or_(
                Soldier.name.contains(search),
                Soldier.military_id.contains(search),
                Soldier.specialty.contains(search)
            )
        )
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    soldiers_list = query.order_by(Soldier.name).all()
    
    return render_template('soldiers.html', soldiers=soldiers_list, search=search, status_filter=status_filter)

@app.route('/soldiers/add', methods=['GET', 'POST'])
@login_required
def add_soldier():
    if request.method == 'POST':
        try:
            soldier = Soldier(
                name=request.form['name'],
                military_id=request.form['military_id'],
                enlistment_date=datetime.strptime(request.form['enlistment_date'], '%Y-%m-%d').date(),
                specialty=request.form.get('specialty', ''),
                status=request.form.get('status', 'Active'),
                exemption_no_duty=bool(request.form.get('exemption_no_duty')),
                exemption_no_shaving=bool(request.form.get('exemption_no_shaving')),
                exemption_no_boots=bool(request.form.get('exemption_no_boots'))
            )
            
            db.session.add(soldier)
            db.session.commit()
            
            log_activity('add_soldier', 'soldier', soldier.id, 
                        f'Added soldier: {soldier.name} ({soldier.military_id})')
            
            flash(f'Soldier {soldier.name} added successfully!', 'success')
            return redirect(url_for('soldiers'))
            
        except Exception as e:
            flash(f'Error adding soldier: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('add_soldier.html')

@app.route('/soldiers/<int:soldier_id>/edit', methods=['GET', 'POST'])
def edit_soldier(soldier_id):
    soldier = Soldier.query.get_or_404(soldier_id)
    
    if request.method == 'POST':
        try:
            soldier.name = request.form['name']
            soldier.military_id = request.form['military_id']
            soldier.enlistment_date = datetime.strptime(request.form['enlistment_date'], '%Y-%m-%d').date()
            soldier.specialty = request.form.get('specialty', '')
            soldier.status = request.form.get('status', 'Active')
            soldier.exemption_no_duty = bool(request.form.get('exemption_no_duty'))
            soldier.exemption_no_shaving = bool(request.form.get('exemption_no_shaving'))
            soldier.exemption_no_boots = bool(request.form.get('exemption_no_boots'))
            
            db.session.commit()
            flash(f'Soldier {soldier.name} updated successfully!', 'success')
            return redirect(url_for('soldiers'))
            
        except Exception as e:
            flash(f'Error updating soldier: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('edit_soldier.html', soldier=soldier)

@app.route('/soldiers/<int:soldier_id>/delete', methods=['POST'])
def delete_soldier(soldier_id):
    soldier = Soldier.query.get_or_404(soldier_id)
    try:
        db.session.delete(soldier)
        db.session.commit()
        flash(f'Soldier {soldier.name} deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting soldier: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('soldiers'))

@app.route('/duties')
def duties():
    duty_types = DutyType.query.filter_by(is_active=True).all()
    return render_template('duties.html', duty_types=duty_types)

@app.route('/duties/add', methods=['POST'])
def add_duty_type():
    try:
        duty_type = DutyType(
            name=request.form['name'],
            description=request.form.get('description', ''),
            team_size=int(request.form.get('team_size', 1)),
            shifts_per_day=int(request.form.get('shifts_per_day', 1))
        )
        
        db.session.add(duty_type)
        db.session.commit()
        
        # Add default time slots based on shifts_per_day
        if duty_type.shifts_per_day == 3:
            # Standard 3-shift pattern
            time_slots = [
                (1, "15:00", "18:00"),
                (1, "00:00", "02:00"),
                (1, "06:00", "09:00"),
                (2, "18:00", "21:00"),
                (2, "02:00", "04:00"),
                (2, "09:00", "12:00"),
                (3, "21:00", "00:00"),
                (3, "04:00", "06:00"),
                (3, "12:00", "15:00")
            ]
        else:
            # Single shift - full day
            time_slots = [(1, "08:00", "18:00")]
        
        for shift_num, start_time, end_time in time_slots:
            slot = DutyTimeSlot(
                duty_type_id=duty_type.id,
                shift_number=shift_num,
                start_time=start_time,
                end_time=end_time
            )
            db.session.add(slot)
        
        db.session.commit()
        flash(f'Duty type {duty_type.name} added successfully!', 'success')
        
    except Exception as e:
        flash(f'Error adding duty type: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('duties'))

@app.route('/schedule')
def schedule():
    selected_date = request.args.get('date')
    if selected_date:
        try:
            schedule_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            schedule_date = date.today()
    else:
        schedule_date = date.today()
    
    # Get existing assignments for the date
    assignments = db.session.query(DutyAssignment, Soldier, DutyType).join(
        Soldier, DutyAssignment.soldier_id == Soldier.id
    ).join(
        DutyType, DutyAssignment.duty_type_id == DutyType.id
    ).filter(
        DutyAssignment.duty_date == schedule_date
    ).order_by(DutyType.name, DutyAssignment.shift_number).all()
    
    # Check if schedule exists for this date
    schedule_obj = DutySchedule.query.filter_by(schedule_date=schedule_date).first()
    
    return render_template('schedule.html', 
                         assignments=assignments, 
                         schedule_date=schedule_date,
                         schedule_obj=schedule_obj)

@app.route('/schedule/generate', methods=['POST'])
def generate_schedule():
    selected_date = request.form.get('date')
    if selected_date:
        try:
            schedule_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'error')
            return redirect(url_for('schedule'))
    else:
        schedule_date = date.today()
    
    try:
        scheduler = SimpleScheduler()
        success = scheduler.generate_daily_schedule(schedule_date)
        
        if success:
            log_activity('generate_schedule', 'schedule', None, 
                        f'Generated schedule for {schedule_date.strftime("%d/%m/%Y")}')
            flash(f'Schedule generated successfully for {schedule_date}!', 'success')
        else:
            flash('Failed to generate complete schedule. Check soldier availability.', 'warning')
            
    except Exception as e:
        flash(f'Error generating schedule: {str(e)}', 'error')
        logging.error(f"Schedule generation error: {e}")
    
    return redirect(url_for('schedule', date=schedule_date.strftime('%Y-%m-%d')))

@app.route('/schedule/clear', methods=['POST'])
def clear_schedule():
    selected_date = request.form.get('date')
    if selected_date:
        try:
            schedule_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'error')
            return redirect(url_for('schedule'))
    else:
        schedule_date = date.today()
    
    try:
        # Clear all assignments for the date
        DutyAssignment.query.filter_by(duty_date=schedule_date).delete()
        
        # Remove schedule record
        schedule_obj = DutySchedule.query.filter_by(schedule_date=schedule_date).first()
        if schedule_obj:
            db.session.delete(schedule_obj)
        
        db.session.commit()
        flash(f'Schedule cleared for {schedule_date}!', 'success')
        
    except Exception as e:
        flash(f'Error clearing schedule: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('schedule', date=schedule_date.strftime('%Y-%m-%d')))

@app.route('/duty_sheet')
def duty_sheet():
    selected_date = request.args.get('date')
    if selected_date:
        try:
            sheet_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            sheet_date = date.today()
    else:
        sheet_date = date.today()
    
    # Get all assignments for the date, organized by duty type and shift
    assignments = db.session.query(DutyAssignment, Soldier, DutyType).join(
        Soldier, DutyAssignment.soldier_id == Soldier.id
    ).join(
        DutyType, DutyAssignment.duty_type_id == DutyType.id
    ).filter(
        DutyAssignment.duty_date == sheet_date
    ).order_by(DutyType.name, DutyAssignment.shift_number, DutyAssignment.position_in_team).all()
    
    # Organize assignments by duty type and shift
    organized_duties = {}
    for assignment, soldier, duty_type in assignments:
        if duty_type.name not in organized_duties:
            organized_duties[duty_type.name] = {}
        
        shift_key = f"Shift {assignment.shift_number}"
        if shift_key not in organized_duties[duty_type.name]:
            organized_duties[duty_type.name][shift_key] = []
        
        # Get time slot information
        time_slot = assignment.get_time_slot()
        time_info = f"{time_slot.start_time}-{time_slot.end_time}" if time_slot else ""
        
        organized_duties[duty_type.name][shift_key].append({
            'soldier': soldier,
            'assignment': assignment,
            'time_info': time_info
        })
    
    return render_template('duty_sheet.html', 
                         organized_duties=organized_duties,
                         sheet_date=sheet_date,
                         print_mode=request.args.get('print') == 'true')

@app.route('/duty_sheet/print')
def print_duty_sheet():
    selected_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    return redirect(url_for('duty_sheet', date=selected_date, print='true'))
