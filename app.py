from flask import Flask, render_template, request, redirect, session
from mem0 import MemoryClient
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

def get_client():
    api_key = session.get('api_key')
    return MemoryClient(api_key=api_key) if api_key else None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['api_key'] = request.form.get('api_key')
        return redirect('/dashboard')
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    client = get_client()
    if not client:
        return redirect('/')
    
    try:
        users_response = client.users()
        users = [{
            'id': user['name'],
            'type': user['type'],
            'memory_count': user['total_memories'],
            'created': user['created_at']
        } for user in users_response.get('results', [])]
        
        return render_template('dashboard.html', 
                            users=users,
                            stats={
                                'total_users': users_response.get('total_users', 0),
                                'total_agents': users_response.get('total_agents', 0),
                                'memory_count': users_response.get('total_memories', 0)
                            })
    
    except Exception as e:
        return f"Error: {str(e)}"

from collections import Counter
from datetime import datetime
@app.route('/user/<user_id>')
def user_memories(user_id):
    client = get_client()
    if not client:
        return redirect('/')
    
    try:
        page = request.args.get('page', 1, type=int)
        memories_response = client.get_all(user_id=user_id, page=page, page_size=10)
        
        processed_memories = []
        mood_counts = {}
        location_counts = {}
        date_counts = {}

        for memory in memories_response.get('results', []):
            mood = memory['metadata'].get('mood')
            location = memory['metadata'].get('location', {}).get('city')
            timestamp = memory['metadata'].get('timestamp', '')[:10]  # just the date

            # Count mood
            if mood:
                mood_counts[mood] = mood_counts.get(mood, 0) + 1
            # Count location
            if location:
                location_counts[location] = location_counts.get(location, 0) + 1
            # Count date
            if timestamp:
                date_counts[timestamp] = date_counts.get(timestamp, 0) + 1

            processed_memories.append({
                'id': memory['id'],
                'text': memory['memory'],
                'created': memory['created_at'],
                'metadata': {
                    'mood': mood,
                    'location': location,
                    'timestamp': timestamp
                }
            })

        pagination = {
            'current_page': page,
            'total_pages': (memories_response['count'] // 10) + 1,
            'has_next': memories_response['next'] is not None,
            'has_prev': page > 1
        }

        chart_data = {
            'mood_counts': mood_counts,
            'location_counts': location_counts,
            'date_counts': date_counts
        }

        return render_template(
            'memories.html',
            memories=processed_memories,
            user_id=user_id,
            pagination=pagination,
            chart_data=chart_data
        )

    except Exception as e:
        return f"Error: {str(e)}"


@app.route('/delete-memory/<memory_id>', methods=['POST'])
def delete_memory(memory_id):
    client = get_client()
    if client:
        client.delete(memory_id)
    return redirect(request.referrer)

@app.route('/delete-user/<user_id>', methods=['POST'])
def delete_user(user_id):
    client = get_client()
    if client:
        client.delete_all(user_id=user_id)
    return redirect('/dashboard')

@app.route('/add-memory/<user_id>', methods=['POST'])
def add_memory(user_id):
    client = get_client()
    if client and (text := request.form.get('memory_text')):
        client.add([{"role": "user", "content": text}], user_id=user_id)
    return redirect(f'/user/{user_id}')

if __name__ == '__main__':
    app.run(debug=True)
