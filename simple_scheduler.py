import random
from datetime import datetime, date, timedelta
from app import db
from models import Soldier, DutyType, DutyAssignment, DutySchedule

class SimpleScheduler:
    def __init__(self):
        pass
    
    def generate_daily_schedule(self, schedule_date):
        """Generate a comprehensive duty schedule for a specific date"""
        try:
            # Clear existing assignments for the date
            DutyAssignment.query.filter_by(duty_date=schedule_date).delete()
            
            # Get all active duty types
            duty_types = DutyType.query.filter_by(is_active=True).all()
            
            # Get all available soldiers
            available_soldiers = Soldier.query.filter_by(status='Active', exemption_no_duty=False).all()
            
            if not available_soldiers:
                return False
            
            # Shuffle soldiers for randomness
            random.shuffle(available_soldiers)
            
            assignments_created = 0
            soldier_index = 0
            
            # Assign multiple shifts for each duty type
            for duty_type in duty_types:
                # Create 3 shifts per duty type for comprehensive coverage
                for shift_num in [1, 2, 3]:
                    for position in range(duty_type.team_size):
                        if soldier_index >= len(available_soldiers):
                            soldier_index = 0  # Wrap around to reuse soldiers
                        
                        soldier = available_soldiers[soldier_index]
                        
                        assignment = DutyAssignment(
                            soldier_id=soldier.id,
                            duty_type_id=duty_type.id,
                            duty_date=schedule_date,
                            shift_number=shift_num,
                            position_in_team=position + 1,
                            notes=f"Auto-assigned by scheduler"
                        )
                        
                        db.session.add(assignment)
                        assignments_created += 1
                        soldier_index += 1
            
            # Create schedule record
            schedule_obj = DutySchedule.query.filter_by(schedule_date=schedule_date).first()
            if not schedule_obj:
                schedule_obj = DutySchedule(
                    schedule_date=schedule_date,
                    notes=f"Auto-generated schedule with {assignments_created} assignments"
                )
                db.session.add(schedule_obj)
            
            schedule_obj.is_finalized = True
            
            db.session.commit()
            return True
            
        except Exception as e:
            print(f"Error generating schedule: {e}")
            db.session.rollback()
            return False