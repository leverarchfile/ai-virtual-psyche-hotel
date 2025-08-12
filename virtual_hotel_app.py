import os
import json
import random
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, g
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'virtual-hotel-secret-key')

# Database setup
DATABASE = 'virtual_hotel.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                position_x INTEGER NOT NULL,
                position_y INTEGER NOT NULL,
                location_city TEXT NOT NULL,
                location_country TEXT NOT NULL,
                sleep_duration REAL NOT NULL,
                skin_temperature REAL NOT NULL,
                heart_rate INTEGER NOT NULL,
                light_switches TEXT NOT NULL,
                ambient_temperature REAL NOT NULL,
                wifi_connections TEXT NOT NULL,
                internet_traffic TEXT NOT NULL,
                ai_interpretation TEXT NOT NULL,
                color_theme TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS hotel_state (
                id INTEGER PRIMARY KEY,
                grid_size INTEGER NOT NULL,
                occupied_positions TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS api_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                room_id TEXT NOT NULL,
                model_used TEXT NOT NULL,
                api_provider TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time_ms INTEGER,
                error_message TEXT
            );
            
            INSERT OR REPLACE INTO hotel_state (id, grid_size, occupied_positions) 
            VALUES (1, 15, '[]');
        ''')
        db.commit()

# Initialize Anthropic Claude
try:
    anthropic_client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
except Exception:
    anthropic_client = None
    print("Warning: No Anthropic API key found - using contextual fallback interpretations")

@dataclass
class DataStream:
    local_time: str
    location: Dict[str, str]  # city, country
    sleep_duration: float  # hours
    skin_temperature: float  # celsius
    heart_rate: int  # bpm
    light_switches: List[str]  # which lights are on
    ambient_temperature: float  # celsius
    wifi_connections: List[str]  # device names
    internet_traffic: Dict[str, float]  # type: GB

class VirtualHotel:
    def __init__(self):
        # Don't initialize database in __init__ - do it lazily
        self._initialized = False
        
    def init_database(self):
        """Initialize database and create sample rooms if empty"""
        if self._initialized:
            return
            
        init_db()
        db = get_db()
        
        # Check if we have any rooms
        existing_rooms = db.execute('SELECT COUNT(*) as count FROM rooms').fetchone()
        if existing_rooms['count'] == 0:
            # Create sample rooms
            for i in range(6):
                self.create_sample_room()
        
        self._initialized = True
    
    def create_sample_room(self):
        """Create a sample room with mock data"""
        # Generate room_id first
        room_id = str(uuid.uuid4())
        user_id = f"demo_user_{random.randint(1000, 9999)}"
        
        data_stream = self.generate_mock_data_stream()
        position = self.find_available_position()
        ai_interpretation = self.get_ai_interpretation(data_stream, room_id)
        color_theme = self.generate_color_theme()
        
        db = get_db()
        
        db.execute('''
            INSERT INTO rooms (
                id, user_id, position_x, position_y,
                location_city, location_country, sleep_duration,
                skin_temperature, heart_rate, light_switches,
                ambient_temperature, wifi_connections, internet_traffic,
                ai_interpretation, color_theme
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            room_id, user_id, position['x'], position['y'],
            data_stream.location['city'], data_stream.location['country'],
            data_stream.sleep_duration, data_stream.skin_temperature,
            data_stream.heart_rate, json.dumps(data_stream.light_switches),
            data_stream.ambient_temperature, json.dumps(data_stream.wifi_connections),
            json.dumps(data_stream.internet_traffic), ai_interpretation, color_theme
        ))
        db.commit()
        
        # Update occupied positions
        self.update_occupied_positions()
        
    def generate_mock_data_stream(self) -> DataStream:
        """Generate realistic mock data for demonstration"""
        cities = [
            {"city": "Tokyo", "country": "Japan"},
            {"city": "New York", "country": "USA"},
            {"city": "London", "country": "UK"},
            {"city": "Berlin", "country": "Germany"},
            {"city": "São Paulo", "country": "Brazil"},
            {"city": "Mumbai", "country": "India"},
            {"city": "Sydney", "country": "Australia"},
        ]
        
        light_options = [
            ["bedroom main", "desk lamp"],
            ["living room", "kitchen"],
            ["bathroom", "hallway"],
            ["bedroom main", "bedside lamp", "closet"],
            ["kitchen", "dining room"],
            ["desk lamp", "ambient lighting"],
        ]
        
        wifi_devices = [
            ["laptop", "smartphone", "television"],
            ["smartphone", "tablet", "speaker"],
            ["laptop", "smartphone", "console"],
            ["smartphone", "watch", "tablet"],
            ["laptop", "speaker", "lights"],
        ]
        
        traffic_types = ["social media", "streaming", "work", "gaming", "browsing"]
        
        return DataStream(
            local_time=datetime.now().strftime("%H:%M"),
            location=random.choice(cities),
            sleep_duration=round(random.uniform(4.5, 9.5), 1),
            skin_temperature=round(random.uniform(32.0, 37.5), 1),
            heart_rate=random.randint(55, 95),
            light_switches=random.choice(light_options),
            ambient_temperature=round(random.uniform(18.0, 26.0), 1),
            wifi_connections=random.choice(wifi_devices),
            internet_traffic={t: round(random.uniform(0.1, 5.0), 2) for t in random.sample(traffic_types, 3)}
        )
    
    def get_ai_interpretation(self, data_stream: DataStream, room_id: str = None) -> str:
        """Generate AI interpretation of the room's psychic interiority using Claude"""
        prompt = f"""Write a poetic, atmospheric interpretation of this person's psychic interiority. Use around 200 words to create a vivid, dreamlike portrait of their inner state based on the biometric and digital data. Be lyrical and evocative:

Location: {data_stream.location['city']}, {data_stream.location['country']}
Local Time: {data_stream.local_time}
Sleep Duration: {data_stream.sleep_duration} hours
Skin Temperature: {data_stream.skin_temperature}°C
Heart Rate: {data_stream.heart_rate} bpm
Active Lights: {', '.join(data_stream.light_switches)}
Room Temperature: {data_stream.ambient_temperature}°C
Connected Devices: {', '.join(data_stream.wifi_connections)}
Internet Traffic: {', '.join([f'{k}: {v}GB' for k, v in data_stream.internet_traffic.items()])}

Write approximately 200 words of poetic interpretation."""

        start_time = datetime.now()
        model_used = "claude-3-haiku-20240307"
        api_provider = "anthropic"
        
        try:
            if anthropic_client and anthropic_client.api_key:
                message = anthropic_client.messages.create(
                    model=model_used,
                    max_tokens=300,
                    temperature=0.8,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                end_time = datetime.now()
                response_time = int((end_time - start_time).total_seconds() * 1000)
                
                # Log successful API call
                if room_id:
                    self.log_api_call(room_id, model_used, api_provider, "success", response_time)
                
                result = message.content[0].text.strip()
                return result
        except Exception as e:
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Log failed API call
            if room_id:
                self.log_api_call(room_id, model_used, api_provider, "error", response_time, str(e))
            
            print(f"Claude API error: {e}")
        
        # Log fallback usage
        if room_id:
            self.log_api_call(room_id, "contextual-fallback", "local", "fallback", 0)
        
        # Rich fallback interpretations based on data patterns
        return self.generate_contextual_interpretation(data_stream)
    
    def log_api_call(self, room_id: str, model_used: str, api_provider: str, status: str, response_time_ms: int, error_message: str = None):
        """Log API call details"""
        db = get_db()
        db.execute('''
            INSERT INTO api_logs (room_id, model_used, api_provider, status, response_time_ms, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (room_id, model_used, api_provider, status, response_time_ms, error_message))
        db.commit()
    
    def get_api_logs(self, limit: int = 20):
        """Get recent API call logs"""
        db = get_db()
        logs = db.execute('''
            SELECT * FROM api_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,)).fetchall()
        
        return [dict(log) for log in logs]
    
    def get_service_info(self):
        """Get service desk information"""
        if anthropic_client and anthropic_client.api_key:
            ai_model = "claude-3-haiku-20240307"
            ai_status = "Connected"
        else:
            ai_model = "contextual-fallback"
            ai_status = "Using Fallback"
        
        return {
            "ai_model": ai_model,
            "ai_status": ai_status,
            "api_logs": self.get_api_logs(10)
        }
    
    def generate_contextual_interpretation(self, data_stream: DataStream) -> str:
        """Generate contextual interpretations based on actual data patterns (max 180 chars)"""
        interpretations = []
        
        # Sleep-based interpretations
        if data_stream.sleep_duration < 6:
            interpretations.extend([
                "Restless thoughts weave through digital twilight. Sleep-deprived synapses seek solace in connected glow.",
                "Insufficient dreams echo through biometric whispers. Neural pathways dance between exhaustion and possibility.",
                "Fragments of interrupted sleep pulse through room. Soul navigates fatigue with electric determination."
            ])
        elif data_stream.sleep_duration > 8:
            interpretations.extend([
                "Deep rest restored spirit's equilibrium. Well-rested consciousness flows through digital networks.",
                "Abundant sleep manifests in steady vitals. Dreams processed, mind emerges clear and centered.",
                "Restorative slumber charged flesh and spirit. Room pulses with quiet confidence and inner peace."
            ])
        
        # Heart rate interpretations
        if data_stream.heart_rate > 80:
            interpretations.extend([
                "Elevated pulses reveal inner fire burning. Cardiovascular symphony speaks of excitement and anticipation.",
                "Rapid heartbeats echo through digital chambers. Life force flows with caffeinated or passionate intensity.",
                "Acceleration rhythms pulse through sensors. Spirit in motion, driven by invisible currents of purpose."
            ])
        elif data_stream.heart_rate < 70:
            interpretations.extend([
                "Calm cardiovascular rhythms suggest contemplation. Heart beats with steady cadence of meditation.",
                "Measured pulses reflect inner tranquility. Digital environment mirrors soul in harmony with time.",
                "Gentle cardiac rhythms whisper contentment. Biometric signature of consciousness at complete ease."
            ])
        
        # Time-based interpretations
        time_hour = int(data_stream.local_time.split(':')[0])
        if time_hour >= 22 or time_hour <= 5:
            interpretations.extend([
                "Nocturnal energies suffuse digital space. Night thoughts flow through fiber optic dreams and silence.",
                "Deep hour consciousness explores territories. Room becomes vessel for midnight introspection rituals.",
                "Late hour geometry manifests in screens. Privacy and possibility merge in darkness sanctuary."
            ])
        elif time_hour >= 6 and time_hour <= 10:
            interpretations.extend([
                "Morning light mingles with artificial glow. Awakening mind calibrates against digital possibilities.",
                "Dawn consciousness emerges through interfaces. Fresh pathways align with new day potential rhythms.",
                "Early hours bring networked soul clarity. Room hums with quiet productivity of fresh beginnings."
            ])
        
        # Default atmospheric interpretations
        default_interpretations = [
            "Consciousness flickers like overhead lights. Soul navigates between virtual and visceral realities.",
            "Biometric whispers reveal spirit transition. Space between wakefulness becomes digital portal gateway.",
            "Temperature fluctuations mirror emotional currents. Each device pulses with seeking consciousness rhythm.",
            "Digital signatures trace invisible thoughts. Room echoes with private experience poetry and resonance.",
            "Electromagnetic fields carry intention. Technology expresses inner weather through connected interfaces.",
            "Data streams paint digital appetite portraits. Mind hungers for connection, creation, and meaning."
        ]
        interpretations.extend(default_interpretations)
        
        # Ensure we stay within character limit
        selected = random.choice(interpretations)
        return selected[:180] if len(selected) > 180 else selected
    
    def get_occupied_positions(self):
        """Get currently occupied positions from database"""
        db = get_db()
        positions = db.execute('SELECT position_x, position_y FROM rooms').fetchall()
        return {(pos['position_x'], pos['position_y']) for pos in positions}
    
    def update_occupied_positions(self):
        """Update the occupied positions in hotel_state table"""
        occupied = list(self.get_occupied_positions())
        db = get_db()
        db.execute(
            'UPDATE hotel_state SET occupied_positions = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1',
            (json.dumps(occupied),)
        )
        db.commit()
    
    def get_grid_size(self):
        """Get current grid size from database"""
        db = get_db()
        result = db.execute('SELECT grid_size FROM hotel_state WHERE id = 1').fetchone()
        return result['grid_size'] if result else 15
    
    def expand_grid(self, new_size):
        """Expand the grid size in database"""
        db = get_db()
        db.execute(
            'UPDATE hotel_state SET grid_size = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1',
            (new_size,)
        )
        db.commit()
    
    def find_available_position(self) -> Dict[str, int]:
        """Find an available position in the hotel grid"""
        occupied = self.get_occupied_positions()
        grid_size = self.get_grid_size()
        
        for x in range(grid_size):
            for y in range(grid_size):
                if (x, y) not in occupied:
                    return {"x": x, "y": y}
        
        # Expand grid if needed
        new_grid_size = grid_size + 5
        self.expand_grid(new_grid_size)
        return {"x": new_grid_size - 1, "y": new_grid_size - 1}
    
    def generate_color_theme(self) -> str:
        """Generate a color theme based on data patterns"""
        themes = ["primary", "secondary", "tertiary", "quaternary", "accent"]
        return random.choice(themes)
    
    def check_in_user(self, user_id: str) -> str:
        """Check in a new user and create their room"""
        self.init_database()  # Ensure database is initialized
        db = get_db()
        
        # Check if user already has a room
        existing = db.execute('SELECT id FROM rooms WHERE user_id = ?', (user_id,)).fetchone()
        if existing:
            return None
        
        room_id = str(uuid.uuid4())
        data_stream = self.generate_mock_data_stream()
        position = self.find_available_position()
        ai_interpretation = self.get_ai_interpretation(data_stream, room_id)
        color_theme = self.generate_color_theme()
        
        db.execute('''
            INSERT INTO rooms (
                id, user_id, position_x, position_y,
                location_city, location_country, sleep_duration,
                skin_temperature, heart_rate, light_switches,
                ambient_temperature, wifi_connections, internet_traffic,
                ai_interpretation, color_theme
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            room_id, user_id, position['x'], position['y'],
            data_stream.location['city'], data_stream.location['country'],
            data_stream.sleep_duration, data_stream.skin_temperature,
            data_stream.heart_rate, json.dumps(data_stream.light_switches),
            data_stream.ambient_temperature, json.dumps(data_stream.wifi_connections),
            json.dumps(data_stream.internet_traffic), ai_interpretation, color_theme
        ))
        db.commit()
        
        self.update_occupied_positions()
        return room_id
    
    def check_out_user(self, user_id: str):
        """Check out a user and remove their room"""
        db = get_db()
        db.execute('DELETE FROM rooms WHERE user_id = ?', (user_id,))
        db.commit()
        self.update_occupied_positions()
    
    def get_hotel_state(self) -> Dict:
        """Get current state of all rooms"""
        self.init_database()  # Ensure database is initialized
        db = get_db()
        rooms = db.execute('SELECT * FROM rooms ORDER BY created_at').fetchall()
        
        room_list = []
        for room in rooms:
            room_dict = {
                'id': room['id'],
                'user_id': room['user_id'],
                'position': {'x': room['position_x'], 'y': room['position_y']},
                'data_stream': {
                    'local_time': datetime.now().strftime("%H:%M"),
                    'location': {'city': room['location_city'], 'country': room['location_country']},
                    'sleep_duration': room['sleep_duration'],
                    'skin_temperature': room['skin_temperature'],
                    'heart_rate': room['heart_rate'],
                    'light_switches': json.loads(room['light_switches']),
                    'ambient_temperature': room['ambient_temperature'],
                    'wifi_connections': json.loads(room['wifi_connections']),
                    'internet_traffic': json.loads(room['internet_traffic'])
                },
                'ai_interpretation': room['ai_interpretation'],
                'color_theme': room['color_theme'],
                'last_updated': room['updated_at']
            }
            room_list.append(room_dict)
        
        return {
            "rooms": room_list,
            "total_occupancy": len(room_list),
            "grid_size": self.get_grid_size()
        }
    
    def update_room_data(self, room_id: str):
        """Update a room's data stream while preserving core identity"""
        db = get_db()
        room = db.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
        
        if room:
            # Generate slight variations while keeping location constant
            new_sleep = max(3, min(12, room['sleep_duration'] + random.uniform(-0.5, 0.5)))
            new_skin_temp = max(30, min(40, room['skin_temperature'] + random.uniform(-1, 1)))
            new_heart_rate = max(50, min(120, room['heart_rate'] + random.randint(-5, 5)))
            new_ambient_temp = max(15, min(30, room['ambient_temperature'] + random.uniform(-1, 1)))
            
            # Create updated data stream
            data_stream = DataStream(
                local_time=datetime.now().strftime("%H:%M"),
                location={'city': room['location_city'], 'country': room['location_country']},
                sleep_duration=new_sleep,
                skin_temperature=new_skin_temp,
                heart_rate=new_heart_rate,
                light_switches=json.loads(room['light_switches']),
                ambient_temperature=new_ambient_temp,
                wifi_connections=json.loads(room['wifi_connections']),
                internet_traffic=json.loads(room['internet_traffic'])
            )
            
            ai_interpretation = self.get_ai_interpretation(data_stream, room_id)
            
            db.execute('''
                UPDATE rooms SET 
                    sleep_duration = ?, skin_temperature = ?, heart_rate = ?,
                    ambient_temperature = ?, ai_interpretation = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_sleep, new_skin_temp, new_heart_rate, new_ambient_temp, ai_interpretation, room_id))
            db.commit()

# Global hotel instance - will be initialized lazily
hotel = VirtualHotel()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_in', methods=['POST'])
def check_in():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    room_id = hotel.check_in_user(session['user_id'])
    if room_id:
        session['room_id'] = room_id
        return jsonify({"status": "success", "room_id": room_id})
    else:
        return jsonify({"status": "error", "message": "Already checked in"})

@app.route('/check_out', methods=['POST'])
def check_out():
    if 'user_id' in session:
        hotel.check_out_user(session['user_id'])
        session.pop('room_id', None)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Not checked in"})

@app.route('/hotel_state')
def get_hotel_state():
    user_room_id = session.get('room_id', None)
    hotel_data = hotel.get_hotel_state()
    hotel_data['user_room_id'] = user_room_id
    return jsonify(hotel_data)

@app.route('/room/<room_id>')
def get_room_details(room_id):
    db = get_db()
    room = db.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    
    if room:
        room_dict = {
            'id': room['id'],
            'user_id': room['user_id'],
            'position': {'x': room['position_x'], 'y': room['position_y']},
            'data_stream': {
                'local_time': datetime.now().strftime("%H:%M"),
                'location': {'city': room['location_city'], 'country': room['location_country']},
                'sleep_duration': room['sleep_duration'],
                'skin_temperature': room['skin_temperature'],
                'heart_rate': room['heart_rate'],
                'light_switches': json.loads(room['light_switches']),
                'ambient_temperature': room['ambient_temperature'],
                'wifi_connections': json.loads(room['wifi_connections']),
                'internet_traffic': json.loads(room['internet_traffic'])
            },
            'ai_interpretation': room['ai_interpretation'],
            'color_theme': room['color_theme'],
            'last_updated': room['updated_at']
        }
        return jsonify(room_dict)
    return jsonify({"error": "Room not found"}), 404

@app.route('/service_desk')
def get_service_desk():
    return jsonify(hotel.get_service_info())

@app.route('/update_room/<room_id>', methods=['POST'])
def update_room(room_id):
    hotel.update_room_data(room_id)
    return jsonify({"status": "success"})

def create_html_template():
    """Create the HTML template file"""
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Virtual Hotel</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 50%, #0d0d0d 100%);
            color: #c0c0c0;
            overflow: hidden;
            height: 100vh;
        }
        
        .header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: linear-gradient(90deg, #000000, #1a1a1a);
            padding: 15px 25px;
            border-bottom: 2px solid #00ff41;
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .title {
            font-size: 20px;
            font-weight: bold;
            color: #00ff41;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        .controls {
            display: flex;
            gap: 15px;
        }
        
        .btn {
            padding: 10px 20px;
            background: linear-gradient(145deg, #2a2a2a, #1a1a1a);
            border: 2px solid #00ff41;
            color: #00ff41;
            cursor: pointer;
            font-family: inherit;
            font-weight: bold;
            text-transform: uppercase;
            transition: all 0.3s;
            clip-path: polygon(10px 0%, 100% 0%, calc(100% - 10px) 100%, 0% 100%);
        }
        
        .btn:hover {
            background: linear-gradient(145deg, #00ff41, #00cc33);
            color: #000000;
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.5);
            transform: translateY(-2px);
        }
        
        .hotel-container {
            position: absolute;
            top: 80px;
            left: 0;
            right: 0;
            bottom: 0;
            overflow: auto;
            padding: 25px;
        }
        
        .hotel-container.service-desk-open {
            bottom: 250px;
        }
        
        .hotel-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .room {
            width: 140px;
            height: 140px;
            border: 2px solid;
            padding: 12px;
            cursor: pointer;
            transition: all 0.4s ease;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            clip-path: polygon(15px 0%, 100% 0%, calc(100% - 15px) 100%, 0% 100%);
        }
        
        .room:hover {
            transform: scale(1.08) translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 255, 65, 0.3);
        }
        
        .room.primary,
        .room.secondary,
        .room.tertiary,
        .room.quaternary,
        .room.accent {
            background: linear-gradient(135deg, #2a2a2a, #404040);
            border-color: #808080;
        }
        
        .room.user-room {
            background: linear-gradient(135deg, #003300, #004d00);
            border-color: #00ff41;
            box-shadow: 0 0 15px rgba(0, 255, 65, 0.4);
        }
        
        .room-number {
            font-size: 10px;
            opacity: 0.8;
            color: #00ff41;
            text-transform: uppercase;
        }
        
        .room-status {
            font-size: 9px;
            text-align: center;
            opacity: 0.9;
            color: #c0c0c0;
        }
        
        .room-pulse {
            position: absolute;
            top: 50%;
            left: 50%;
            width: 8px;
            height: 8px;
            background: #00ff41;
            transform: translate(-50%, -50%);
            animation: pulse 3s infinite;
        }
        
        @keyframes pulse {
            0% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
            50% { transform: translate(-50%, -50%) scale(2); opacity: 0.3; }
            100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            z-index: 3000;
            align-items: center;
            justify-content: center;
        }
        
        .modal-content {
            background: linear-gradient(135deg, #1a1a1a, #2a2a2a);
            padding: 30px;
            max-width: 700px;
            max-height: 85vh;
            overflow-y: auto;
            border: 2px solid #00ff41;
            position: relative;
            clip-path: polygon(20px 0%, 100% 0%, calc(100% - 20px) 100%, 0% 100%);
        }
        
        .close {
            position: absolute;
            top: 15px;
            right: 20px;
            font-size: 24px;
            cursor: pointer;
            color: #00ff41;
            font-weight: bold;
        }
        
        .close:hover {
            color: #ffffff;
        }
        
        .modal-title {
            color: #00ff41;
            font-size: 18px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 20px;
        }
        
        .data-streams {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .data-item {
            background: linear-gradient(145deg, #0d0d0d, #1a1a1a);
            padding: 12px;
            border-left: 3px solid #00ff41;
            clip-path: polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%);
        }
        
        .data-label {
            color: #00ff41;
            font-size: 11px;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .data-value {
            font-size: 13px;
            color: #e0e0e0;
        }
        
        .ai-interpretation {
            background: linear-gradient(145deg, #001a00, #003300);
            padding: 20px;
            border: 2px solid #00ff41;
            margin: 25px 0;
            font-style: italic;
            line-height: 1.6;
            color: #e0e0e0;
            clip-path: polygon(15px 0%, 100% 0%, calc(100% - 15px) 100%, 0% 100%);
            min-height: 150px;
            max-height: 300px;
            overflow-y: auto;
            font-size: 14px;
        }
        
        .ai-interpretation::before {
            content: "PSYCHIC INTERIORITY STREAM";
            display: block;
            color: #00ff41;
            font-size: 10px;
            font-style: normal;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            opacity: 0.8;
        }
        
        .occupancy-info {
            position: fixed;
            bottom: 25px;
            right: 25px;
            background: linear-gradient(145deg, #1a1a1a, #0d0d0d);
            padding: 12px 18px;
            border: 2px solid #00ff41;
            font-size: 11px;
            color: #00ff41;
            text-transform: uppercase;
            letter-spacing: 1px;
            clip-path: polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%);
            z-index: 500;
            transition: bottom 0.3s ease;
        }
        
        .occupancy-info.service-desk-open {
            bottom: 275px;
        }
        
        .service-desk {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(90deg, #0d0d0d, #1a1a1a);
            border-top: 2px solid #00ff41;
            padding: 15px 25px;
            height: 250px;
            overflow-y: auto;
            z-index: 2000;
            transform: translateY(100%);
            transition: transform 0.3s ease;
        }
        
        .service-desk.open {
            transform: translateY(0);
        }
        
        .service-desk-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .service-desk-title {
            color: #00ff41;
            font-size: 14px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .service-desk-toggle {
            position: fixed;
            bottom: 15px;
            left: 25px;
            background: linear-gradient(145deg, #1a1a1a, #0d0d0d);
            border: 2px solid #00ff41;
            color: #00ff41;
            padding: 8px 16px;
            cursor: pointer;
            font-family: inherit;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
            clip-path: polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%);
            z-index: 2500;
            transition: all 0.3s ease;
        }
        
        .service-desk-toggle:hover {
            background: linear-gradient(145deg, #00ff41, #00cc33);
            color: #000000;
        }
        
        .service-desk-toggle.open {
            bottom: 265px;
        }
        
        .service-info {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }
        
        .ai-model-info {
            background: linear-gradient(145deg, #001a00, #003300);
            padding: 12px;
            border: 1px solid #00ff41;
            clip-path: polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%);
        }
        
        .model-label {
            color: #00ff41;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        
        .model-value {
            color: #e0e0e0;
            font-size: 12px;
        }
        
        .api-logs {
            background: linear-gradient(145deg, #0d0d0d, #1a1a1a);
            padding: 12px;
            border: 1px solid #00ff41;
            clip-path: polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%);
            max-height: 180px;
            overflow-y: auto;
        }
        
        .log-header {
            color: #00ff41;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        
        .log-entry {
            font-size: 10px;
            color: #c0c0c0;
            margin-bottom: 4px;
            border-bottom: 1px solid #333;
            padding-bottom: 4px;
        }
        
        .log-time {
            color: #00ff41;
        }
        
        .log-room {
            color: #808080;
        }
        
        .log-status {
            color: #00ff41;
        }
        
        .log-status.error {
            color: #ff4444;
        }
        
        .log-status.fallback {
            color: #ffaa00;
        }
        
        .status-message {
            position: fixed;
            top: 90px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(145deg, #1a1a1a, #0d0d0d);
            padding: 12px 25px;
            border: 2px solid #00ff41;
            display: none;
            z-index: 2500;
            clip-path: polygon(10px 0%, 100% 0%, calc(100% - 10px) 100%, 0% 100%);
        }
        
        .update-btn {
            margin-top: 20px;
            width: 100%;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Virtual Hotel</div>
        <div class="controls">
            <button class="btn" onclick="checkIn()">Check In</button>
            <button class="btn" onclick="checkOut()">Check Out</button>
            <button class="btn" onclick="loadHotel()">Refresh</button>
        </div>
    </div>
    
    <div class="hotel-container" id="hotelContainer">
        <div class="hotel-grid" id="hotelGrid">
            <!-- Rooms will be dynamically loaded here -->
        </div>
    </div>
    
    <div class="occupancy-info" id="occupancyInfo">
        Occupancy: 0/15
    </div>
    
    <button class="service-desk-toggle" id="serviceDeskToggle" onclick="toggleServiceDesk()">
        Service Desk
    </button>
    
    <div class="service-desk" id="serviceDesk">
        <div class="service-desk-header">
            <div class="service-desk-title">System Status</div>
        </div>
        <div class="service-info" id="serviceInfo">
            <!-- Service info will be loaded here -->
        </div>
    </div>
    
    <div class="modal" id="roomModal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div class="modal-title" id="modalTitle">Room Details</div>
            <div class="data-streams" id="dataStreams">
                <!-- Room data will be populated here -->
            </div>
            <div class="ai-interpretation" id="aiInterpretation">
                <!-- AI interpretation will be populated here -->
            </div>
            <button class="btn update-btn" onclick="updateRoomData()">Update Data Stream</button>
        </div>
    </div>
    
    <div class="status-message" id="statusMessage"></div>

    <script>
        let currentRoomId = null;
        let serviceDeskOpen = false;
        
        function showStatus(message, duration = 3000) {
            const statusDiv = document.getElementById('statusMessage');
            statusDiv.textContent = message;
            statusDiv.style.display = 'block';
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, duration);
        }
        
        async function checkIn() {
            try {
                const response = await fetch('/check_in', { method: 'POST' });
                const data = await response.json();
                if (data.status === 'success') {
                    showStatus('Checked in successfully');
                    loadHotel();
                } else {
                    showStatus(data.message || 'Check-in failed');
                }
            } catch (error) {
                showStatus('Error checking in');
            }
        }
        
        async function checkOut() {
            try {
                const response = await fetch('/check_out', { method: 'POST' });
                const data = await response.json();
                showStatus(data.status === 'success' ? 'Checked out successfully' : 'Check-out failed');
                loadHotel();
            } catch (error) {
                showStatus('Error checking out');
            }
        }
        
        async function loadHotel() {
            try {
                const response = await fetch('/hotel_state');
                const data = await response.json();
                
                const grid = document.getElementById('hotelGrid');
                grid.innerHTML = '';
                
                data.rooms.forEach(room => {
                    const roomDiv = document.createElement('div');
                    // Use user-room class for user's room, otherwise use the original color theme
                    const roomClass = (data.user_room_id && room.id === data.user_room_id) 
                        ? 'user-room' 
                        : room.color_theme;
                    roomDiv.className = `room ${roomClass}`;
                    roomDiv.onclick = () => openRoomModal(room.id);
                    
                    const location = `${room.data_stream.location.city}, ${room.data_stream.location.country}`;
                    const truncatedId = room.id.substring(0, 8);
                    
                    roomDiv.innerHTML = `
                        <div class="room-number">${truncatedId}</div>
                        <div class="room-status">${location}</div>
                        <div class="room-pulse"></div>
                    `;
                    
                    grid.appendChild(roomDiv);
                });
                
                document.getElementById('occupancyInfo').textContent = 
                    `Occupancy: ${data.total_occupancy}/${data.grid_size}`;
                
            } catch (error) {
                showStatus('Error loading hotel data');
            }
        }
        
        async function openRoomModal(roomId) {
            currentRoomId = roomId;
            try {
                const response = await fetch(`/room/${roomId}`);
                const room = await response.json();
                
                document.getElementById('modalTitle').textContent = 
                    `Room ${room.id.substring(0, 8)} - ${room.data_stream.location.city}`;
                
                const dataStreams = document.getElementById('dataStreams');
                dataStreams.innerHTML = `
                    <div class="data-item">
                        <div class="data-label">Location</div>
                        <div class="data-value">${room.data_stream.location.city}, ${room.data_stream.location.country}</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Local Time</div>
                        <div class="data-value">${room.data_stream.local_time}</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Sleep Duration</div>
                        <div class="data-value">${room.data_stream.sleep_duration} hours</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Skin Temperature</div>
                        <div class="data-value">${room.data_stream.skin_temperature}°C</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Heart Rate</div>
                        <div class="data-value">${room.data_stream.heart_rate} bpm</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Room Temperature</div>
                        <div class="data-value">${room.data_stream.ambient_temperature}°C</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Active Lights</div>
                        <div class="data-value">${room.data_stream.light_switches.join(', ')}</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Connected Devices</div>
                        <div class="data-value">${room.data_stream.wifi_connections.join(', ')}</div>
                    </div>
                    <div class="data-item">
                        <div class="data-label">Internet Traffic</div>
                        <div class="data-value">${Object.entries(room.data_stream.internet_traffic).map(([k,v]) => `${k}: ${v}GB`).join(', ')}</div>
                    </div>
                `;
                
                document.getElementById('aiInterpretation').textContent = room.ai_interpretation;
                document.getElementById('roomModal').style.display = 'flex';
                
            } catch (error) {
                showStatus('Error loading room details');
            }
        }
        
        function closeModal() {
            document.getElementById('roomModal').style.display = 'none';
        }
        
        async function updateRoomData() {
            if (!currentRoomId) return;
            
            try {
                const response = await fetch(`/update_room/${currentRoomId}`, { method: 'POST' });
                const data = await response.json();
                if (data.status === 'success') {
                    showStatus('Room data updated');
                    openRoomModal(currentRoomId); // Refresh modal
                    loadHotel(); // Refresh grid
                }
            } catch (error) {
                showStatus('Error updating room data');
            }
        }
        
        async function toggleServiceDesk() {
            serviceDeskOpen = !serviceDeskOpen;
            const serviceDesk = document.getElementById('serviceDesk');
            const toggle = document.getElementById('serviceDeskToggle');
            const hotelContainer = document.getElementById('hotelContainer');
            const occupancyInfo = document.getElementById('occupancyInfo');
            
            if (serviceDeskOpen) {
                serviceDesk.classList.add('open');
                toggle.classList.add('open');
                hotelContainer.classList.add('service-desk-open');
                occupancyInfo.classList.add('service-desk-open');
                toggle.textContent = 'Close Desk';
                
                // Load service info
                try {
                    const response = await fetch('/service_desk');
                    const data = await response.json();
                    
                    const serviceInfo = document.getElementById('serviceInfo');
                    serviceInfo.innerHTML = `
                        <div class="ai-model-info">
                            <div class="model-label">AI Model</div>
                            <div class="model-value">${data.ai_model}</div>
                            <div class="model-label">Status</div>
                            <div class="model-value">${data.ai_status}</div>
                        </div>
                        <div class="api-logs">
                            <div class="log-header">Recent API Calls</div>
                            ${data.api_logs.map(log => `
                                <div class="log-entry">
                                    <span class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</span> |
                                    <span class="log-room">${log.room_id ? log.room_id.substring(0, 8) : 'N/A'}</span> |
                                    <span class="log-status ${log.status}">${log.status}</span> |
                                    ${log.model_used} (${log.response_time_ms || 0}ms)
                                </div>
                            `).join('')}
                        </div>
                    `;
                } catch (error) {
                    showStatus('Error loading service desk info');
                }
            } else {
                serviceDesk.classList.remove('open');
                toggle.classList.remove('open');
                hotelContainer.classList.remove('service-desk-open');
                occupancyInfo.classList.remove('service-desk-open');
                toggle.textContent = 'Service Desk';
            }
        }
        
        // Load hotel data on page load
        document.addEventListener('DOMContentLoaded', loadHotel);
        
        // Auto-refresh every 30 seconds
        setInterval(loadHotel, 30000);
    </script>
</body>
</html>'''
    
    return html_content

if __name__ == '__main__':
    # Create templates directory and HTML template
    os.makedirs('templates', exist_ok=True)
    
    # Write the HTML template to file
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(create_html_template())
    
    app.run(debug=True, port=5000)