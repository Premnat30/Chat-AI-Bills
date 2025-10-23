from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_socketio import SocketIO, emit
from database import db, User, Bill, BillParticipant, ChatMessage, Friend
from datetime import datetime, date
import os
import json
import csv
from io import StringIO

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///bills.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize database
with app.app_context():
    db.create_all()

# Mock AI response function
def get_ai_response(message, bill_context=None):
    message_lower = message.lower()
    
    if any(word in message_lower for word in ['hello', 'hi', 'hey']):
        return "Hello! I'm your bill sharing assistant. I can help you split bills, track expenses, manage friends, and generate reports."
    
    elif any(word in message_lower for word in ['split', 'divide', 'share']):
        return "I can help you split bills! Use the bill creation form to add a new bill with friends, visit details, and automatic calculations."
    
    elif any(word in message_lower for word in ['friend', 'friends']):
        return "You can manage your friends list in the Friends section. Add friends with their contact details to easily include them in bills."
    
    elif any(word in message_lower for word in ['csv', 'export', 'download', 'report']):
        return "I can help you download CSV reports! Go to the Bills section to download overall reports or individual friend summaries."
    
    elif any(word in message_lower for word in ['total', 'amount', 'cost']):
        return "I automatically calculate totals including tax and discounts. Create a bill and I'll handle all the math for you!"
    
    elif any(word in message_lower for word in ['thanks', 'thank you']):
        return "You're welcome! Let me know if you need help with bill splitting, friend management, or CSV exports."
    
    else:
        return "I'm here to help with bill sharing! You can create bills with friends, track visit details, split expenses, and download CSV reports. Try asking about managing friends or exporting data."

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chat'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username)
                db.session.add(user)
                db.session.commit()
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    bills = Bill.query.filter_by(created_by=session['user_id']).all()
    friends = Friend.query.filter_by(user_id=session['user_id']).all()
    return render_template('chat.html', username=session['username'], bills=bills, friends=friends)

@app.route('/bills')
def bills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_bills = Bill.query.filter_by(created_by=session['user_id']).all()
    return render_template('bills.html', bills=user_bills)

@app.route('/friends')
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_friends = Friend.query.filter_by(user_id=session['user_id']).all()
    user_bills = Bill.query.filter_by(created_by=session['user_id']).all()
    
    return render_template('friends.html', friends=user_friends, bills=user_bills)

@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    
    if not name:
        return jsonify({'error': 'Friend name is required'}), 400
    
    friend = Friend(
        user_id=session['user_id'],
        name=name,
        email=email,
        phone=phone
    )
    db.session.add(friend)
    db.session.commit()
    
    return jsonify({'success': True, 'friend': {
        'id': friend.id,
        'name': friend.name,
        'email': friend.email,
        'phone': friend.phone
    }})

@app.route('/delete_friend/<int:friend_id>', methods=['DELETE'])
def delete_friend(friend_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    friend = Friend.query.filter_by(id=friend_id, user_id=session['user_id']).first()
    if not friend:
        return jsonify({'error': 'Friend not found'}), 404
    
    db.session.delete(friend)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/create_bill', methods=['POST'])
def create_bill():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    description = data.get('description')
    visit_details = data.get('visit_details')
    visit_date_str = data.get('visit_date')
    total_amount = data.get('total_amount')
    tax_amount = data.get('tax_amount', 0)
    discount_amount = data.get('discount_amount', 0)
    participants = data.get('participants', [])
    
    if not all([description, visit_date_str, total_amount]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
        final_amount = float(total_amount) + float(tax_amount) - float(discount_amount)
        
        # Create bill
        bill = Bill(
            description=description,
            visit_details=visit_details,
            visit_date=visit_date,
            total_amount=float(total_amount),
            tax_amount=float(tax_amount),
            discount_amount=float(discount_amount),
            final_amount=final_amount,
            created_by=session['user_id']
        )
        db.session.add(bill)
        db.session.flush()
        
        # Add participants
        for participant in participants:
            bill_participant = BillParticipant(
                bill_id=bill.id,
                friend_id=participant['friend_id'],
                amount_owed=float(participant['amount_owed'])
            )
            db.session.add(bill_participant)
        
        db.session.commit()
        
        return jsonify({'success': True, 'bill_id': bill.id})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download_csv')
def download_csv():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Create CSV data
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Bill Report - Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    
    # Write overall bills summary
    writer.writerow(['OVERALL BILLS SUMMARY'])
    writer.writerow(['Description', 'Visit Date', 'Visit Details', 'Total Amount', 'Tax', 'Discount', 'Final Amount'])
    
    bills = Bill.query.filter_by(created_by=session['user_id']).all()
    total_overall = 0
    
    for bill in bills:
        writer.writerow([
            bill.description,
            bill.visit_date.strftime('%Y-%m-%d'),
            bill.visit_details or '',
            f"${bill.total_amount:.2f}",
            f"${bill.tax_amount:.2f}",
            f"${bill.discount_amount:.2f}",
            f"${bill.final_amount:.2f}"
        ])
        total_overall += bill.final_amount
    
    writer.writerow(['', '', '', '', '', 'TOTAL:', f"${total_overall:.2f}"])
    writer.writerow([])
    
    # Write individual friends summary
    writer.writerow(['INDIVIDUAL FRIENDS SUMMARY'])
    writer.writerow(['Friend Name', 'Total Amount Owed', 'Number of Bills', 'Average per Bill'])
    
    friends = Friend.query.filter_by(user_id=session['user_id']).all()
    
    for friend in friends:
        participant_bills = BillParticipant.query.join(Bill).filter(
            BillParticipant.friend_id == friend.id,
            Bill.created_by == session['user_id']
        ).all()
        
        total_owed = sum(p.amount_owed for p in participant_bills)
        num_bills = len(participant_bills)
        avg_per_bill = total_owed / num_bills if num_bills > 0 else 0
        
        writer.writerow([
            friend.name,
            f"${total_owed:.2f}",
            num_bills,
            f"${avg_per_bill:.2f}" if num_bills > 0 else '$0.00'
        ])
    
    writer.writerow([])
    
    # Write detailed bill breakdown
    writer.writerow(['DETAILED BILL BREAKDOWN'])
    writer.writerow(['Bill', 'Visit Date', 'Friend', 'Amount Owed'])
    
    for bill in bills:
        for participant in bill.participants:
            writer.writerow([
                bill.description,
                bill.visit_date.strftime('%Y-%m-%d'),
                participant.friend.name,
                f"${participant.amount_owed:.2f}"
            ])
    
    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=bill_report.csv"}
    )

@app.route('/download_friend_csv/<int:friend_id>')
def download_friend_csv(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friend = Friend.query.filter_by(id=friend_id, user_id=session['user_id']).first()
    if not friend:
        return "Friend not found", 404
    
    # Create CSV data for individual friend
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([f'Bill Report for {friend.name} - Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    
    # Write friend details
    writer.writerow(['FRIEND DETAILS'])
    writer.writerow(['Name:', friend.name])
    writer.writerow(['Email:', friend.email or 'N/A'])
    writer.writerow(['Phone:', friend.phone or 'N/A'])
    writer.writerow([])
    
    # Write bills involving this friend
    writer.writerow(['BILLS INVOLVING THIS FRIEND'])
    writer.writerow(['Description', 'Visit Date', 'Visit Details', 'Total Bill Amount', 'Amount Owed by Friend'])
    
    participant_bills = BillParticipant.query.join(Bill).filter(
        BillParticipant.friend_id == friend.id,
        Bill.created_by == session['user_id']
    ).all()
    
    total_owed = 0
    
    for participant in participant_bills:
        bill = participant.bill
        writer.writerow([
            bill.description,
            bill.visit_date.strftime('%Y-%m-%d'),
            bill.visit_details or '',
            f"${bill.final_amount:.2f}",
            f"${participant.amount_owed:.2f}"
        ])
        total_owed += participant.amount_owed
    
    writer.writerow([])
    writer.writerow(['TOTAL AMOUNT OWED:', '', '', '', f"${total_owed:.2f}"])
    
    # Prepare response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={friend.name}_bill_report.csv"}
    )

@socketio.on('send_message')
def handle_send_message(data):
    if 'user_id' not in session:
        return
    
    message = data.get('message', '').strip()
    bill_id = data.get('bill_id')
    
    if message:
        # Save user message
        user_message = ChatMessage(
            bill_id=bill_id if bill_id else 1,
            user_id=session['user_id'],
            message=message
        )
        db.session.add(user_message)
        
        # Get AI response
        ai_response = get_ai_response(message)
        
        # Save AI response as system message
        system_user = User.query.filter_by(username='system').first()
        if not system_user:
            system_user = User(username='system')
            db.session.add(system_user)
            db.session.flush()
        
        ai_message = ChatMessage(
            bill_id=bill_id if bill_id else 1,
            user_id=system_user.id,
            message=ai_response
        )
        db.session.add(ai_message)
        db.session.commit()
        
        # Emit messages to all clients
        emit('new_message', {
            'user': session['username'],
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'user'
        }, broadcast=True)
        
        emit('new_message', {
            'user': 'Bill Assistant',
            'message': ai_response,
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'ai'
        }, broadcast=True)

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        emit('user_joined', {'username': session['username']}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)