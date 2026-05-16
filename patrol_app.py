from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import smtplib
import pymysql
import os
pymysql.install_as_MySQLdb()

app = Flask(__name__)
CORS(app)

# ✅ Reads from Railway environment variable
db_url = os.environ.get('DATABASE_URL', '')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'patrolsecure_secret_2024'

db = SQLAlchemy(app)

EMAIL_ADDRESS  = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"
SMTP_SERVER    = "smtp.gmail.com"
SMTP_PORT      = 587

# ============================================================
#  MODELS
# ============================================================

class Teacher(db.Model):
    __tablename__ = 'teachers'
    id          = db.Column(db.Integer,      primary_key=True, autoincrement=True)
    name        = db.Column(db.String(255),  nullable=False)
    teacher_id  = db.Column(db.String(50),   unique=True, nullable=False)
    email       = db.Column(db.String(255),  unique=True, nullable=False)
    phone       = db.Column(db.String(50),   nullable=False)
    department  = db.Column(db.String(100),  nullable=False)
    password    = db.Column(db.String(255),  nullable=False)
    device_name = db.Column(db.String(255),  nullable=True)
    latitude    = db.Column(db.Numeric(10,7),nullable=True)
    longitude   = db.Column(db.Numeric(10,7),nullable=True)
    role        = db.Column(db.String(20),   default='teacher')
    created_at  = db.Column(db.DateTime,     default=datetime.utcnow)

class ActiveSession(db.Model):
    __tablename__ = 'active_sessions'
    id          = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    email       = db.Column(db.String(255), nullable=False)
    device_name = db.Column(db.String(255), nullable=True)
    login_time  = db.Column(db.DateTime,    default=datetime.utcnow)

class AccessRequest(db.Model):
    __tablename__ = 'access_requests'
    id           = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    email        = db.Column(db.String(255),   nullable=False)
    device_name  = db.Column(db.String(255),   nullable=False)
    latitude     = db.Column(db.Numeric(10,7), nullable=True)
    longitude    = db.Column(db.Numeric(10,7), nullable=True)
    request_time = db.Column(db.DateTime,      default=datetime.utcnow)
    status       = db.Column(db.String(20),    default='Pending')

class PatrolReport(db.Model):
    __tablename__ = 'patrol_reports'
    id              = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    student_name    = db.Column(db.String(255), nullable=False)
    register_number = db.Column(db.String(100), nullable=False)
    department      = db.Column(db.String(100), nullable=False)
    year_section    = db.Column(db.String(50),  nullable=False)
    issue_type      = db.Column(db.String(100), nullable=False)
    location        = db.Column(db.String(255), nullable=False)
    remarks         = db.Column(db.Text,        nullable=True)
    reported_by     = db.Column(db.String(50),  nullable=False)
    teacher_name    = db.Column(db.String(255), nullable=False)
    status          = db.Column(db.String(20),  default='Open')
    date_time       = db.Column(db.DateTime,    default=datetime.utcnow)

class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    id           = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    teacher_id   = db.Column(db.String(50),  nullable=False)
    teacher_name = db.Column(db.String(255), nullable=False)
    email        = db.Column(db.String(255), nullable=False)
    device_name  = db.Column(db.String(255), nullable=False)
    login_time   = db.Column(db.DateTime,    default=datetime.utcnow)
    status       = db.Column(db.String(20),  default='Success')
    fail_reason  = db.Column(db.String(255), nullable=True)

class Student(db.Model):
    __tablename__ = 'students'
    id              = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    name            = db.Column(db.String(255), nullable=False)
    register_number = db.Column(db.String(100), unique=True, nullable=False)
    department      = db.Column(db.String(100), nullable=False)
    year            = db.Column(db.String(10),  nullable=False)
    section         = db.Column(db.String(10),  nullable=False)
    phone           = db.Column(db.String(50),  nullable=True)

# ============================================================
#  HELPER FUNCTIONS
# ============================================================

def send_email(to_email, subject, body):
    try:
        full_message = f"Subject: {subject}\n\n{body}"
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, full_message)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_access_request_alert(admin_email, requester_email, device_name):
    subject = "PatrolSecure: New Device Access Request"
    body = f"""A teacher has requested access from a new device.

Email      : {requester_email}
Device     : {device_name}
Time       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please log in to the admin panel to Approve or Reject this request.

-- PatrolSecure System
"""
    return send_email(admin_email, subject, body)

def send_approval_email(teacher_email, device_name, approved):
    if approved:
        subject = "PatrolSecure: Device Access Approved"
        body = f"""Your access request has been approved.

Device: {device_name}

You can now log in from this device.

-- PatrolSecure Admin
"""
    else:
        subject = "PatrolSecure: Device Access Rejected"
        body = f"""Your access request has been rejected.

Device: {device_name}

Please contact your administrator for more information.

-- PatrolSecure Admin
"""
    return send_email(teacher_email, subject, body)

def location_matches(db_lat, db_lng, req_lat, req_lng, threshold_km=1.0):
    if db_lat is None or db_lng is None:
        return True
    if req_lat is None or req_lng is None:
        return False

    import math
    lat1  = float(db_lat)
    lng1  = float(db_lng)
    lat2  = float(req_lat)
    lng2  = float(req_lng)

    dlat  = abs(lat1 - lat2) * 111.0
    dlng  = abs(lng1 - lng2) * 111.0 * math.cos(math.radians((lat1 + lat2) / 2))
    dist  = math.sqrt(dlat**2 + dlng**2)

    return dist <= threshold_km

# ============================================================
#  ROUTES
# ============================================================

@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()

        required = ['name', 'teacher_id', 'email', 'phone', 'department',
                    'password', 'confirm_password', 'device_name']
        if not data or not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400

        if data['password'] != data['confirm_password']:
            return jsonify({'error': 'Passwords do not match'}), 400

        if Teacher.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 409

        if Teacher.query.filter_by(teacher_id=data['teacher_id']).first():
            return jsonify({'error': 'Teacher ID already registered'}), 409

        hashed = generate_password_hash(data['password'])

        teacher = Teacher(
            name        = data['name'],
            teacher_id  = data['teacher_id'],
            email       = data['email'],
            phone       = data['phone'],
            department  = data['department'],
            password    = hashed,
            device_name = data['device_name'],
            latitude    = data.get('latitude'),
            longitude   = data.get('longitude'),
            role        = 'teacher'
        )

        db.session.add(teacher)
        db.session.commit()

        return jsonify({'message': 'Teacher registered successfully'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password required'}), 400

        email       = data['email']
        password    = data['password']
        device_name = data.get('device_name', '')
        req_lat     = data.get('latitude')
        req_lng     = data.get('longitude')

        teacher = Teacher.query.filter_by(email=email).first()

        if not teacher:
            return jsonify({'error': 'Invalid credentials'}), 401

        if not check_password_hash(teacher.password, password):
            db.session.add(LoginHistory(
                teacher_id   = teacher.teacher_id,
                teacher_name = teacher.name,
                email        = email,
                device_name  = device_name,
                status       = 'Failed',
                fail_reason  = 'Wrong password'
            ))
            db.session.commit()
            return jsonify({'error': 'Invalid credentials'}), 401

        if teacher.role != 'admin':

            if teacher.device_name and teacher.device_name.strip().lower() != device_name.strip().lower():
                db.session.add(LoginHistory(
                    teacher_id   = teacher.teacher_id,
                    teacher_name = teacher.name,
                    email        = email,
                    device_name  = device_name,
                    status       = 'Failed',
                    fail_reason  = 'Device mismatch'
                ))
                db.session.commit()
                return jsonify({
                    'error'  : 'Device not registered for this account',
                    'code'   : 'DEVICE_MISMATCH',
                    'message': 'Request access to use this device'
                }), 403

            if not location_matches(teacher.latitude, teacher.longitude, req_lat, req_lng):
                db.session.add(LoginHistory(
                    teacher_id   = teacher.teacher_id,
                    teacher_name = teacher.name,
                    email        = email,
                    device_name  = device_name,
                    status       = 'Failed',
                    fail_reason  = 'Location mismatch'
                ))
                db.session.commit()
                return jsonify({
                    'error'  : 'Login location does not match registered location',
                    'code'   : 'LOCATION_MISMATCH',
                    'message': 'Request access to log in from this location'
                }), 403

        db.session.add(ActiveSession(
            email       = teacher.email,
            device_name = device_name
        ))

        db.session.add(LoginHistory(
            teacher_id   = teacher.teacher_id,
            teacher_name = teacher.name,
            email        = teacher.email,
            device_name  = device_name,
            status       = 'Success'
        ))

        db.session.commit()

        return jsonify({
            'message': 'Login successful',
            'teacher': {
                'id'         : teacher.id,
                'name'       : teacher.name,
                'teacher_id' : teacher.teacher_id,
                'email'      : teacher.email,
                'phone'      : teacher.phone,
                'department' : teacher.department,
                'device_name': teacher.device_name,
                'role'       : teacher.role
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/request_access', methods=['POST'])
def request_access():
    try:
        data = request.get_json()

        if not data or 'email' not in data or 'device_name' not in data:
            return jsonify({'error': 'Email and device name required'}), 400

        req = AccessRequest(
            email       = data['email'],
            device_name = data['device_name'],
            latitude    = data.get('latitude'),
            longitude   = data.get('longitude'),
            status      = 'Pending'
        )
        db.session.add(req)
        db.session.commit()

        admin = Teacher.query.filter_by(role='admin').first()
        if admin:
            send_access_request_alert(admin.email, data['email'], data['device_name'])

        return jsonify({'message': 'Access request submitted. Admin will review shortly.'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/get_current_user', methods=['GET'])
def get_current_user():
    try:
        last = ActiveSession.query.order_by(ActiveSession.id.desc()).first()
        if not last:
            return jsonify({'error': 'No active user found'}), 404

        teacher = Teacher.query.filter_by(email=last.email).first()
        if not teacher:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'email'      : teacher.email,
            'name'       : teacher.name,
            'teacher_id' : teacher.teacher_id,
            'department' : teacher.department,
            'role'       : teacher.role
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/add_report', methods=['POST'])
def add_report():
    try:
        data = request.get_json()

        required = ['student_name', 'register_number', 'department',
                    'year_section', 'issue_type', 'location',
                    'reported_by', 'teacher_name']
        if not data or not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400

        reg = data['register_number'].strip().upper()

        existing_student = Student.query.filter(
            db.func.upper(Student.register_number) == reg
        ).first()

        if not existing_student:
            year_section = data['year_section']
            parts = year_section.split(' - ') if ' - ' in year_section else [year_section, '']
            year    = parts[0].strip()
            section = parts[1].strip() if len(parts) > 1 else '-'

            new_student = Student(
                name            = data['student_name'],
                register_number = reg,
                department      = data['department'],
                year            = year,
                section         = section,
                phone           = data.get('phone', '-')
            )
            db.session.add(new_student)

        report = PatrolReport(
            student_name    = data['student_name'],
            register_number = reg,
            department      = data['department'],
            year_section    = data['year_section'],
            issue_type      = data['issue_type'],
            location        = data['location'],
            remarks         = data.get('remarks', ''),
            reported_by     = data['reported_by'],
            teacher_name    = data['teacher_name'],
            status          = 'Open'
        )
        db.session.add(report)
        db.session.commit()

        return jsonify({'message': 'Report submitted successfully', 'id': report.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/get_reports', methods=['GET'])
def get_reports():
    try:
        reports = PatrolReport.query.order_by(PatrolReport.date_time.desc()).all()
        return jsonify([{
            'id'             : r.id,
            'student_name'   : r.student_name,
            'register_number': r.register_number,
            'department'     : r.department,
            'year_section'   : r.year_section,
            'issue_type'     : r.issue_type,
            'location'       : r.location,
            'remarks'        : r.remarks,
            'reported_by'    : r.reported_by,
            'teacher_name'   : r.teacher_name,
            'status'         : r.status,
            'date_time'      : r.date_time.strftime('%Y-%m-%d %H:%M:%S')
        } for r in reports]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_report_status/<int:report_id>', methods=['PUT'])
def update_report_status(report_id):
    try:
        data   = request.get_json()
        status = data.get('status')

        if status not in ['Open', 'Resolved', 'Pending']:
            return jsonify({'error': 'Invalid status'}), 400

        report = PatrolReport.query.get(report_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        report.status = status
        db.session.commit()
        return jsonify({'message': 'Status updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/search_student/<register_number>', methods=['GET'])
def search_student(register_number):
    try:
        reg = register_number.upper().strip()

        reports = PatrolReport.query.filter(
            db.func.upper(PatrolReport.register_number) == reg
        ).order_by(PatrolReport.date_time.desc()).all()

        student = Student.query.filter(
            db.func.upper(Student.register_number) == reg
        ).first()

        if student:
            student_data = {
                'name'            : student.name,
                'register_number' : student.register_number,
                'department'      : student.department,
                'year'            : student.year,
                'section'         : student.section,
                'phone'           : student.phone or '-'
            }
        elif reports:
            latest = reports[0]
            year_section = latest.year_section
            parts = year_section.split(' - ') if ' - ' in year_section else [year_section, '']
            student_data = {
                'name'            : latest.student_name,
                'register_number' : latest.register_number,
                'department'      : latest.department,
                'year'            : parts[0].strip(),
                'section'         : parts[1].strip() if len(parts) > 1 else '-',
                'phone'           : '-'
            }
        else:
            return jsonify({'error': 'Student not found'}), 404

        return jsonify({
            'student': student_data,
            'reports': [{
                'id'          : r.id,
                'issue_type'  : r.issue_type,
                'location'    : r.location,
                'remarks'     : r.remarks,
                'teacher_name': r.teacher_name,
                'status'      : r.status,
                'date_time'   : r.date_time.strftime('%Y-%m-%d %H:%M:%S')
            } for r in reports],
            'total_reports': len(reports)
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/student_history/<register_number>', methods=['GET'])
def student_history(register_number):
    try:
        reports = PatrolReport.query.filter(
            db.func.upper(PatrolReport.register_number) == register_number.upper().strip()
        ).order_by(PatrolReport.date_time.desc()).all()

        return jsonify([{
            'id'             : r.id,
            'student_name'   : r.student_name,
            'register_number': r.register_number,
            'department'     : r.department,
            'year_section'   : r.year_section,
            'issue_type'     : r.issue_type,
            'location'       : r.location,
            'remarks'        : r.remarks,
            'teacher_name'   : r.teacher_name,
            'status'         : r.status,
            'date_time'      : r.date_time.strftime('%Y-%m-%d %H:%M:%S')
        } for r in reports]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/login_history', methods=['GET'])
def get_login_history():
    try:
        history = LoginHistory.query.order_by(LoginHistory.login_time.desc()).all()
        return jsonify([{
            'id'          : h.id,
            'teacher_id'  : h.teacher_id,
            'teacher_name': h.teacher_name,
            'email'       : h.email,
            'device_name' : h.device_name,
            'login_time'  : h.login_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status'      : h.status,
            'fail_reason' : h.fail_reason
        } for h in history]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/access_requests', methods=['GET'])
def get_access_requests():
    try:
        reqs = AccessRequest.query.order_by(
            AccessRequest.request_time.desc()
        ).all()
        return jsonify([{
            'id'          : r.id,
            'email'       : r.email,
            'device_name' : r.device_name,
            'latitude'    : float(r.latitude)  if r.latitude  else None,
            'longitude'   : float(r.longitude) if r.longitude else None,
            'request_time': r.request_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status'      : r.status
        } for r in reqs]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/access_requests/<int:req_id>', methods=['PUT'])
def update_access_request(req_id):
    try:
        data   = request.get_json()
        action = data.get('status')

        if action not in ['Approved', 'Rejected']:
            return jsonify({'error': 'Invalid action'}), 400

        req = AccessRequest.query.get(req_id)
        if not req:
            return jsonify({'error': 'Request not found'}), 404

        req.status = action
        db.session.commit()

        if action == 'Approved':
            teacher = Teacher.query.filter_by(email=req.email).first()
            if teacher:
                teacher.device_name = req.device_name
                if req.latitude:
                    teacher.latitude  = req.latitude
                if req.longitude:
                    teacher.longitude = req.longitude
                db.session.commit()

        send_approval_email(req.email, req.device_name, action == 'Approved')

        return jsonify({'message': f'Request {action} successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/teacher_profile/<email>', methods=['GET'])
def teacher_profile(email):
    try:
        teacher = Teacher.query.filter_by(email=email).first()
        if not teacher:
            return jsonify({'error': 'Teacher not found'}), 404

        return jsonify({
            'id'         : teacher.id,
            'name'       : teacher.name,
            'teacher_id' : teacher.teacher_id,
            'email'      : teacher.email,
            'phone'      : teacher.phone,
            'department' : teacher.department,
            'device_name': teacher.device_name,
            'role'       : teacher.role
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_profile/<email>', methods=['PUT'])
def update_profile(email):
    try:
        data    = request.get_json()
        teacher = Teacher.query.filter_by(email=email).first()
        if not teacher:
            return jsonify({'error': 'Teacher not found'}), 404

        if 'name'  in data: teacher.name  = data['name']
        if 'phone' in data: teacher.phone = data['phone']

        db.session.commit()
        return jsonify({'message': 'Profile updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/admin/teachers', methods=['GET'])
def get_all_teachers():
    try:
        teachers = Teacher.query.filter_by(role='teacher').all()
        return jsonify([{
            'id'         : t.id,
            'name'       : t.name,
            'teacher_id' : t.teacher_id,
            'email'      : t.email,
            'phone'      : t.phone,
            'department' : t.department,
            'device_name': t.device_name,
            'created_at' : t.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for t in teachers]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/send_alert', methods=['POST'])
def send_alert():
    try:
        data = request.get_json()
        to_email = data.get('email')
        subject  = data.get('subject', 'PatrolSecure Alert')
        body     = data.get('body', '')

        if not to_email:
            return jsonify({'error': 'Email is required'}), 400

        if send_email(to_email, subject, body):
            return jsonify({'message': 'Alert sent successfully'}), 200
        else:
            return jsonify({'error': 'Failed to send alert'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
