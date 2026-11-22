from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'samuel-freight-secret'

GMAIL_USER = "samuelfreightservice@gmail.com"
GMAIL_APP_PASSWORD = "YOUR_APP_PASSWORD_HERE"

def get_db():
    conn = sqlite3.connect('shipments.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT UNIQUE,
                sender_name TEXT,
                sender_phone TEXT,
                sender_address TEXT,
                receiver_name TEXT,
                receiver_phone TEXT,
                receiver_email TEXT,
                receiver_address TEXT,
                package_count TEXT,
                delivery_type TEXT,
                pickup_location TEXT,
                custom_pickup TEXT,
                status TEXT DEFAULT 'Pending',
                created_at TEXT
            )
        ''')
        conn.commit()

init_db()

def generate_tracking_number():
    with get_db() as conn:
        count = conn.execute('SELECT COUNT(*) FROM shipments').fetchone()[0]
        return f"SF{count + 1:05d}"

def send_arrival_email(shipment):
    try:
        if shipment['pickup_location'] == 'Nigeria':
            location_name = "Nigeria Office"
            address = "19 Ajao Road, Ikeja, Lagos, Nigeria"
            phones = "0904 912 4622 / 0812 954 8890 / 0902 336 2725"
        elif shipment['pickup_location'] == 'Canada':
            location_name = "Canada Office"
            address = "445 Redstone Walk NE #202, Calgary, AB T3N 1M5, Canada"
            phones = "+1 587 966 4811 / +1 587 889 0447"
        else:
            location_name = "Pickup Location"
            address = shipment['custom_pickup'] or "Contact us for address"
            phones = "Contact office"

        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = shipment['receiver_email']
        msg['Subject'] = f"Your Shipment is Ready for Pickup! ({shipment['tracking_number']})"

        body = f"""
Dear {shipment['receiver_name']},

Great news! Your shipment has arrived and is now ready for pickup.

TRACKING NUMBER: {shipment['tracking_number']}

SHIPPER: {shipment['sender_name']}
RECEIVER: {shipment['receiver_name']}

PICKUP LOCATION: {location_name}
{address}
Phone: {phones}

Please bring a valid government-issued ID when collecting your shipment.
Contact us before visiting to confirm availability.

Thank you for choosing Samuel Freight Service.

Best regards,
Samuel Freight Service
"""
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email error:", e)
        return False

@app.route('/')
def index():
    return redirect(url_for('list_shipments'))

@app.route('/create', methods=['GET', 'POST'])
def create_shipment():
    if request.method == 'POST':
        tracking = generate_tracking_number()
        data = {
            'tracking_number': tracking,
            'sender_name': request.form['sender_name'],
            'sender_phone': request.form['sender_phone'],
            'sender_address': request.form['sender_address'],
            'receiver_name': request.form['receiver_name'],
            'receiver_phone': request.form['receiver_phone'],
            'receiver_email': request.form['receiver_email'],
            'receiver_address': request.form['receiver_address'],
            'package_count': request.form['package_count'],
            'delivery_type': request.form.get('delivery_type', 'Door-to-Door'),
            'pickup_location': request.form['pickup_location'],
            'custom_pickup': request.form.get('custom_pickup', ''),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        with get_db() as conn:
            conn.execute('''
                INSERT INTO shipments 
                (tracking_number, sender_name, sender_phone, sender_address,
                 receiver_name, receiver_phone, receiver_email, receiver_address,
                 package_count, delivery_type, pickup_location, custom_pickup, created_at)
                VALUES (:tracking_number, :sender_name, :sender_phone, :sender_address,
                        :receiver_name, :receiver_phone, :receiver_email, :receiver_address,
                        :package_count, :delivery_type, :pickup_location, :custom_pickup, :created_at)
            ''', data)
            conn.commit()
        return redirect(url_for('view_label', tracking=tracking))
    return render_template('create.html')

@app.route('/list')
def list_shipments():
    with get_db() as conn:
        shipments = conn.execute('SELECT * FROM shipments ORDER BY id DESC').fetchall()
    return render_template('list.html', shipments=shipments)

@app.route('/label/<tracking>')
def view_label(tracking):
    with get_db() as conn:
        shipment = conn.execute('SELECT * FROM shipments WHERE tracking_number = ?', (tracking,)).fetchone()
    if not shipment:
        return "Shipment not found", 404
    return render_template('label.html', s=shipment)

@app.route('/notify/<tracking>')
def notify_arrived(tracking):
    with get_db() as conn:
        shipment = conn.execute('SELECT * FROM shipments WHERE tracking_number = ?', (tracking,)).fetchone()
        if shipment and shipment['receiver_email']:
            success = send_arrival_email(shipment)
            if success:
                conn.execute('UPDATE shipments SET status = ? WHERE tracking_number = ?', ('Arrived', tracking))
                conn.commit()
                flash('Email sent successfully!', 'success')
            else:
                flash('Failed to send email. Check your Gmail App Password.', 'error')
        else:
            flash('No email address for this shipment.', 'error')
    return redirect(url_for('list_shipments'))

# ========== LIVE TRACKING ==========
@app.route('/track')
def track_page():
    return render_template('track.html')

@app.route('/api/track/<tracking>')
def api_track(tracking):
    tracking = tracking.strip().upper()
    with get_db() as conn:
        shipment = conn.execute(
            'SELECT * FROM shipments WHERE tracking_number = ?', (tracking,)
        ).fetchone()
    
    if not shipment:
        return jsonify({'found': False, 'message': 'Tracking number not found'})
    
    return jsonify({
        'found': True,
        'tracking_number': shipment['tracking_number'],
        'status': shipment['status'],
        'sender_name': shipment['sender_name'],
        'receiver_name': shipment['receiver_name'],
        'receiver_phone': shipment['receiver_phone'],
        'package_count': shipment['package_count'],
        'delivery_type': shipment['delivery_type'],
        'pickup_location': shipment['pickup_location'],
        'custom_pickup': shipment['custom_pickup'],
        'created_at': shipment['created_at']
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)