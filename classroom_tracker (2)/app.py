from flask import Flask, jsonify, render_template
from flask_mysqldb import MySQL
from datetime import datetime
import pytz
from flask import request

app = Flask(__name__)

# Configure MySQL connection
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'classroom_user'
app.config['MYSQL_PASSWORD'] = 'new_secure_password123'  
app.config['MYSQL_DB'] = 'class_occupancy_tracker'

mysql = MySQL(app)

# Routes for pages
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/user-dashboard')
def user_dashboard():
    return render_template('user-dashboard.html')

@app.route('/admin-dashboard')
def admin_dashboard():
    return render_template('admin-dashboard.html')

@app.route('/admin-login')
def admin_login():
    return render_template('admin-login.html')

@app.route('/user-login')
def user_login():
    return render_template('user-login.html')

# API for classroom status
@app.route('/api/rooms')
def api_rooms():
    cur = mysql.connection.cursor()

    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    current_day = now.strftime('%A')
    current_time = now.strftime('%H:%M:%S')

    query = """
        SELECT c.room_id, c.name, c.capacity, c.room_type,
               COALESCE(rs.current_status,
                        CASE
                          WHEN EXISTS (
                            SELECT 1 FROM timetable t
                            WHERE t.room_id = c.room_id
                              AND t.day_of_week = %s
                              AND %s BETWEEN t.start_time AND t.end_time
                          )
                          THEN 'Occupied'
                          ELSE 'Vacant'
                        END
               ) AS status,
               rs.last_updated
        FROM classrooms c
        LEFT JOIN room_status rs ON c.room_id = rs.room_id
    """

    cur.execute(query, (current_day, current_time))
    rows = cur.fetchall()
    cur.close()

    result = []
    for row in rows:
        result.append({
             'room_id': row[0],
            'name': row[1],
            'capacity': row[2],
            'type': row[3],
            'status': row[4],
            'last_updated': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else 'N/A'
        })

    return jsonify(result)

@app.route('/api/manual-update', methods=['POST'])
def manual_update():
    data = request.get_json()
    room_name = data.get('room_name')
    new_status = data.get('status')

    cur = mysql.connection.cursor()
    # Get room_id using room_name
    cur.execute("SELECT room_id FROM classrooms WHERE name = %s", (room_name,))
    result = cur.fetchone()
    room_id = result[0]  

    # Update or insert into room_status
    cur.execute("""
        INSERT INTO room_status (room_id, current_status, updated_by, update_method)
        VALUES (%s, %s, 1, 'manual')
        ON DUPLICATE KEY UPDATE current_status = %s, update_method = 'manual'
    """, (room_id, new_status, new_status))

    mysql.connection.commit()
    cur.close()

    return jsonify({'message': f'{room_name} marked as {new_status}'})

@app.route('/api/add-classroom', methods=['POST'])
def add_classroom():
    data = request.get_json()
    room_id = data['id']
    name = data['name']
    capacity = data['capacity']
    building = data['building']
    floor = data['floor']

    cur = mysql.connection.cursor()

    try:
        cur.execute("""
            INSERT INTO classrooms (room_id, name, capacity, building, floor, room_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (room_id, name, capacity, building, floor, 'Classroom'))

        mysql.connection.commit()
        return jsonify({'message': 'Classroom added successfully'}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'message': 'Error adding classroom', 'error': str(e)}), 500

    finally:
        cur.close()

if __name__ == '__main__':
    app.run(debug=True)
