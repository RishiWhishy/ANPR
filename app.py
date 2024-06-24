from flask import Flask, jsonify, send_from_directory, request
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# MongoDB setup
client = MongoClient('localhost', 27017)
db = client['anpr_database']
registered_vehicles_collection = db['registered_vehicles']
vehicle_logs_collection = db['vehicle_logs']

# Serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Serve the index HTML file
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Serve the vehicle registration HTML file
@app.route('/vehicle-registration.html')
def vehicle_registration():
    return send_from_directory('static', 'vehicle-registration.html')

# Serve the detailed analysis HTML file
@app.route('/detailed-analysis.html')
def detailed_analysis():
    return send_from_directory('static', 'detailed-analysis.html')

# API endpoint for vehicle registration
@app.route('/register_vehicle', methods=['POST'])
def register_vehicle():
    data = request.json
    owner_name = data.get('ownerName')
    vehicle_number = data.get('numberPlate')
    vehicle_model = data.get('vehicleType')  # Ensure consistent field naming
    access_type = data.get('accessType')

    # Insert into MongoDB
    registered_vehicles_collection.insert_one({
        "owner_name": owner_name,
        "vehicle_number": vehicle_number,
        "vehicle_model": vehicle_model,  # Ensure consistent field naming
        "access_type": access_type
    })

    return jsonify({"msg": "Vehicle registered successfully!"})

# API endpoint to get the list of registered vehicles
@app.route('/get_registered_vehicles', methods=['GET'])
def get_registered_vehicles():
    vehicles = list(registered_vehicles_collection.find({}, {'_id': 0}))
    return jsonify(vehicles)

# API endpoint to get today's entry and exit counts
@app.route('/get_todays_entry_exit', methods=['GET'])
def get_todays_entry_exit():
    today = datetime.today().date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    entries = vehicle_logs_collection.count_documents({
        'entry_time': {'$gte': start, '$lt': end}
    })

    exits = vehicle_logs_collection.count_documents({
        'exit_time': {'$gte': start, '$lt': end}
    })

    return jsonify({
        'todays_entry': entries,
        'todays_exit': exits
    })

# API endpoint to get recent detections
@app.route('/get_recent_detections', methods=['GET'])
def get_recent_detections():
    recent_detections = list(vehicle_logs_collection.find().sort('detection_time', -1).limit(10))
    for detection in recent_detections:
        detection['_id'] = str(detection['_id'])
    return jsonify(recent_detections)

# API endpoint to get detection summary
@app.route('/get_detection_summary', methods=['GET'])
def get_detection_summary():
    today = datetime.today().date()
    start_today = datetime.combine(today, datetime.min.time())
    end_today = datetime.combine(today, datetime.max.time())

    start_week = start_today - timedelta(days=start_today.weekday())
    end_week = start_today + timedelta(days=6 - start_today.weekday())

    todays_entry = vehicle_logs_collection.count_documents({
        'entry_time': {'$gte': start_today, '$lt': end_today}
    })

    weekly_entry = vehicle_logs_collection.count_documents({
        'entry_time': {'$gte': start_week, '$lt': end_week}
    })

    return jsonify({
        'todays_entry': todays_entry,
        'weekly_entry': weekly_entry
    })

if __name__ == '__main__':
    app.run(debug=True)

# API endpoint to get detection summary
@app.route('/get_detection_summary', methods=['GET'])
def get_detection_summary():
    today = datetime.today().date()
    start_today = datetime.combine(today, datetime.min.time())
    end_today = datetime.combine(today, datetime.max.time())

    # Start of the week (Monday)
    start_week = start_today - timedelta(days=today.weekday())
    # End of the week (Sunday)
    end_week = start_week + timedelta(days=6)

    todays_entry = vehicle_logs_collection.count_documents({
        'entry_time': {'$gte': start_today, '$lt': end_today}
    })

    weekly_entry = vehicle_logs_collection.count_documents({
        'entry_time': {'$gte': start_week, '$lt': end_week}
    })

    return jsonify({
        'todays_entry': todays_entry,
        'weekly_entry': weekly_entry
    })