"""
Dashboard web application
"""
import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import csv
from io import StringIO, BytesIO
from config import Config
from database import WorkersDatabase, RequestLogsDatabase
from dashboard.auth import login_required, check_credentials
from utils.logger import request_logger

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=Config.DASHBOARD_SESSION_TIMEOUT)

# Database instances
workers_db = WorkersDatabase()
logs_db = RequestLogsDatabase()


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if check_credentials(username, password):
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    """Main dashboard page"""
    # Get statistics
    stats = request_logger.get_stats()
    
    # Get recent logs
    recent_logs = request_logger.get_recent_logs(limit=20)
    
    # Identify important events (events with worker data)
    important_logs = []
    for log in recent_logs:
        response_body = log.get('response_body', {})
        
        # Check if this response contains events
        if isinstance(response_body, dict) and 'events' in response_body:
            events = response_body.get('events', [])
            if events and len(events) > 0:
                # This is an important log with actual events
                log['has_events'] = True
                log['event_count'] = len(events)
                log['event_types'] = [e.get('type') for e in events]
                important_logs.append(log)
    
    # Get worker counts
    all_workers = workers_db.get_all_workers()
    approved_workers = len([w for w in all_workers if w.get('status') == 'approved'])
    blocked_workers = len([w for w in all_workers if w.get('status') == 'blocked'])
    
    return render_template(
        'dashboard.html',
        stats=stats,
        recent_logs=recent_logs[:10],  # Show last 10 for recent activity
        important_logs=important_logs[:5],  # Show last 5 important events
        total_workers=len(all_workers),
        approved_workers=approved_workers,
        blocked_workers=blocked_workers
    )


@app.route('/logs')
@login_required
def logs():
    """Request logs page"""
    # Get filter parameters
    api_target = request.args.get('api_target', '')
    success = request.args.get('success', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    endpoint = request.args.get('endpoint', '')
    limit = int(request.args.get('limit', 100))
    
    # Build filters
    filters = {}
    if api_target:
        filters['api_target'] = api_target
    if success:
        filters['success'] = success == 'true'
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    if endpoint:
        filters['endpoint'] = endpoint
    
    # Get logs
    logs = request_logger.get_recent_logs(limit=limit, filters=filters)
    
    return render_template(
        'logs.html',
        logs=logs,
        filters={
            'api_target': api_target,
            'success': success,
            'start_date': start_date,
            'end_date': end_date,
            'endpoint': endpoint,
            'limit': limit
        }
    )


@app.route('/api/logs')
@login_required
def api_logs():
    """API endpoint for fetching logs (AJAX)"""
    # Get parameters
    limit = int(request.args.get('limit', 100))
    api_target = request.args.get('api_target', '')
    success = request.args.get('success', '')
    
    # Build filters
    filters = {}
    if api_target:
        filters['api_target'] = api_target
    if success:
        filters['success'] = success == 'true'
    
    # Get logs
    logs = request_logger.get_recent_logs(limit=limit, filters=filters)
    
    return jsonify(logs)


@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for fetching statistics"""
    stats = request_logger.get_stats()
    
    # Get worker counts
    all_workers = workers_db.get_all_workers()
    approved_workers = len([w for w in all_workers if w.get('status') == 'approved'])
    blocked_workers = len([w for w in all_workers if w.get('status') == 'blocked'])
    
    stats['total_workers'] = len(all_workers)
    stats['approved_workers'] = approved_workers
    stats['blocked_workers'] = blocked_workers
    
    return jsonify(stats)


@app.route('/workers')
@login_required
def workers():
    """Workers management page"""
    status_filter = request.args.get('status', '')
    
    if status_filter:
        workers_list = workers_db.get_workers_by_status(status_filter)
    else:
        workers_list = workers_db.get_all_workers()
    
    return render_template('workers.html', workers=workers_list, status_filter=status_filter)


@app.route('/export/logs')
@login_required
def export_logs():
    """Export logs as CSV"""
    # Get all logs
    logs = request_logger.get_recent_logs(limit=10000)
    
    # Create CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'timestamp', 'api_target', 'endpoint', 'method', 'status_code',
        'duration_ms', 'success', 'error'
    ])
    
    writer.writeheader()
    for log in logs:
        writer.writerow({
            'timestamp': log.get('timestamp', ''),
            'api_target': log.get('api_target', ''),
            'endpoint': log.get('endpoint', ''),
            'method': log.get('method', ''),
            'status_code': log.get('status_code', ''),
            'duration_ms': log.get('duration_ms', ''),
            'success': log.get('success', ''),
            'error': log.get('error', '')
        })
    
    # Create response
    output.seek(0)
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


@app.route('/export/logs/json')
@login_required
def export_logs_json():
    """Export logs as JSON"""
    logs = request_logger.get_recent_logs(limit=10000)
    
    return send_file(
        BytesIO(json.dumps(logs, indent=2).encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name=f'logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )


def run_dashboard(host='0.0.0.0', port=8080):
    """Run the dashboard application"""
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    run_dashboard(Config.DASHBOARD_HOST, Config.DASHBOARD_PORT)