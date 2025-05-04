from flask import Flask, render_template, request, redirect, session, jsonify
from mem0 import MemoryClient
import os
from datetime import datetime
from collections import Counter

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

@app.route('/search', methods=['GET', 'POST'])
def search_memories():
    client = get_client()
    if not client:
        return redirect('/')
    
    if request.method == 'POST':
        try:
            query = request.form.get('query')
            if not query:
                return "Error: Search query is required", 400
                
            filters = {}
            
            # Build filters based on form data
            if request.form.get('user_id'):
                filters['user_id'] = request.form.get('user_id')
            if request.form.get('agent_id'):
                filters['agent_id'] = request.form.get('agent_id')
            if request.form.get('categories'):
                filters['categories'] = request.form.get('categories').split(',')
            if request.form.get('start_date') and request.form.get('end_date'):
                filters['created_at'] = {
                    'gte': request.form.get('start_date'),
                    'lte': request.form.get('end_date')
                }
            if request.form.get('metadata'):
                try:
                    filters['metadata'] = eval(request.form.get('metadata'))
                except:
                    return "Error: Invalid metadata format. Please provide valid JSON.", 400
            
            # Perform search with filters
            search_response = client.search(
                query=query,
                version="v2",
                filters=filters
            )
            
            # Debug the response structure
            print("Search Response:", search_response)
            
            # Process results to ensure they have the required fields
            processed_results = []
            if isinstance(search_response, dict):
                results = search_response.get('results', [])
            else:
                results = search_response if isinstance(search_response, list) else []
            
            for result in results:
                if isinstance(result, dict):
                    processed_result = {
                        'id': result.get('id', ''),
                        'text': result.get('text', '') or result.get('memory', ''),
                        'created_at': result.get('created_at', ''),
                        'metadata': result.get('metadata', {})
                    }
                    processed_results.append(processed_result)
            
            return render_template('search_results.html', 
                                results=processed_results,
                                query=query)
        
        except Exception as e:
            print("Search Error:", str(e))
            return f"Error: {str(e)}", 500
    
    return render_template('search.html')

@app.route('/memory/<memory_id>')
def memory_details(memory_id):
    client = get_client()
    if not client:
        return redirect('/')
    
    try:
        memory = client.get(memory_id)
        history = client.history(memory_id)
        return render_template('memory_details.html',
                            memory=memory,
                            history=history)
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/update-memory/<memory_id>', methods=['POST'])
def update_memory(memory_id):
    client = get_client()
    if not client:
        return redirect('/')
    
    try:
        new_text = request.form.get('new_text')
        if new_text:
            client.update(memory_id, new_text)
        return redirect(f'/memory/{memory_id}')
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/batch-operations', methods=['GET', 'POST'])
def batch_operations():
    client = get_client()
    if not client:
        return redirect('/')
    
    if request.method == 'POST':
        try:
            operation = request.form.get('operation')
            memories = request.form.get('memory_ids').split(',')
            
            if operation == 'update':
                updates = []
                for memory_id in memories:
                    updates.append({
                        'memory_id': memory_id,
                        'text': request.form.get(f'text_{memory_id}')
                    })
                client.batch_update(updates)
            
            elif operation == 'delete':
                deletes = [{'memory_id': mid} for mid in memories]
                client.batch_delete(deletes)
            
            return redirect('/dashboard')
        
        except Exception as e:
            return f"Error: {str(e)}"
    
    return render_template('batch_operations.html')

def validate_api_key(api_key):
    """Validate the API key by making a test request."""
    try:
        client = MemoryClient(api_key=api_key)
        # Make a simple request to validate the key
        client.users()
        return True
    except Exception:
        return False

@app.route('/api/validate', methods=['POST'])
def validate_key():
    """Endpoint to validate an API key."""
    api_key = request.json.get('api_key')
    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    
    is_valid = validate_api_key(api_key)
    return jsonify({'valid': is_valid})

@app.route('/api/search', methods=['POST'])
def api_search():
    # Check for API key in Authorization header, request body, or session
    api_key = (
        request.headers.get('Authorization', '').replace('Bearer ', '') or
        request.json.get('api_key') or
        session.get('api_key')
    )
    
    if not api_key:
        return jsonify({
            'error': 'No API key found. Please provide it in the Authorization header, request body, or login first.'
        }), 401
    
    if not validate_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        client = MemoryClient(api_key=api_key)
        data = request.json
        query = data.get('query')
        filters = data.get('filters', {})
        
        results = client.search(
            query=query,
            version="v2",
            filters=filters
        )
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/memories', methods=['GET'])
def api_memories():
    # Check for API key in Authorization header, request body, or session
    api_key = (
        request.headers.get('Authorization', '').replace('Bearer ', '') or
        request.args.get('api_key') or
        session.get('api_key')
    )
    
    if not api_key:
        return jsonify({
            'error': 'No API key found. Please provide it in the Authorization header, query parameters, or login first.'
        }), 401
    
    if not validate_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        client = MemoryClient(api_key=api_key)
        filters = {}
        if request.args.get('user_id'):
            filters['user_id'] = request.args.get('user_id')
        if request.args.get('agent_id'):
            filters['agent_id'] = request.args.get('agent_id')
        if request.args.get('categories'):
            filters['categories'] = request.args.get('categories').split(',')
        if request.args.get('start_date') and request.args.get('end_date'):
            filters['created_at'] = {
                'gte': request.args.get('start_date'),
                'lte': request.args.get('end_date')
            }
        
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        
        memories = client.get_all(
            version="v2",
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        return jsonify(memories)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
