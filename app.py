from flask import Flask, render_template, request, redirect, url_for, flash,send_from_directory,send_file,stream_with_context,Response
from camera import CameraManager
from config import Config
import configparser
import threading
import requests
import logging

app = Flask(__name__)
app.config.from_object(Config)
app.logger.setLevel(logging.ERROR)

config = configparser.ConfigParser()
config.read('config.ini')

camera_manager = CameraManager()

@app.route('/')
def index():
    camera_manager.check_storage_space()
    return render_template('index.html',path_rec=config.get('DEFAULT','recording_path'), max_size=int(config.get('DEFAULT','max_space')),consumed_size=camera_manager.get_total_consumed_size())

@app.route('/cameras')
def manage_cameras():
    cameras = camera_manager.get_cameras()
    return render_template('manage_cameras.html', cameras=cameras, camera_manager=camera_manager)

@app.route('/add_camera', methods=['POST'])
def add_camera():
    url = request.form.get('url')
    nickname = request.form.get('nickname')
    if url and nickname:
        camera_manager.add_camera(url, nickname)
        flash('Camera added successfully')
    else:
        flash('Camera URL and nickname are required')
    return redirect(url_for('manage_cameras'))

@app.route('/remove_camera/<int:camera_id>')
def remove_camera(camera_id):
    camera_manager.remove_camera(camera_id)
    flash('Camera removed successfully')
    return redirect(url_for('manage_cameras'))

@app.route('/edit_camera/<int:camera_id>', methods=['POST'])
def edit_camera(camera_id):
    url = request.form.get('url')
    nickname = request.form.get('nickname')
    if url and nickname:
        camera_manager.edit_camera(camera_id, url, nickname)
        flash('Camera updated successfully')
    else:
        flash('Camera URL and nickname are required')
    return redirect(url_for('manage_cameras'))

@app.route('/view_recordings')
def view_recordings():
    recordings,specs = camera_manager.get_recordings()
    return render_template('view_recordings.html', recordings=recordings,specs=specs)

@app.route('/video/<path:path>')
def view_video(path):
    # path = request.args.get('src')  
    return render_template('view_video.html', src=path)

@app.route('/set_recording_path', methods=['POST'])
def set_recording_path():
    path = request.form.get('path')
    camera_manager.set_recording_path(path)
    flash('Recording path set successfully')
    return redirect(url_for('index'))

@app.route('/set_max_space', methods=['POST'])
def set_max_space():
    max_space = request.form.get('max_space')
    camera_manager.set_max_space(int(max_space))
    flash('Max space set successfully')
    return redirect(url_for('index'))

@app.route('/play/<path:path>')
def render_file(path):
    return send_file(path,as_attachment=True)
    # return send_from_directory(config.get('DEFAULT','recording_path'),filename, as_attachment=True)

@app.route("/player/<path:path>")
def streamed_proxy(path):
    r = requests.get('/'+path, stream=True)
    return Response(r.iter_content(chunk_size=10*1024),
                    content_type=r.headers['Content-Type'])

@app.route('/flush_recording/<int:camera_id>')
def flush_recording(camera_id):
    camera_manager.flush_recording(camera_id)
    flash('Recording flushed successfully')
    return redirect(url_for('manage_cameras'))

@app.route('/start_recording/<int:camera_id>')
def start_recording(camera_id):
    thread = threading.Thread(target=camera_manager.start_recording, args=(camera_id,))
    thread.start()
    flash('Recording started successfully')
    return redirect(url_for('manage_cameras'))

@app.route('/stop_recording/<int:camera_id>')
def stop_recording(camera_id):
    camera_manager.stop_recording(camera_id)
    flash('Recording stopped successfully')
    return redirect(url_for('manage_cameras'))

@app.route('/view_last_recording/<int:camera_id>')
def view_last_recording(camera_id):
    recordings = camera_manager.get_recordings()
    if camera_id in recordings and recordings[camera_id]:
        last_recording = recordings[camera_id][-1]
        return redirect(url_for('static', filename=last_recording))
    else:
        flash('No recordings found for this camera')
        return redirect(url_for('manage_cameras'))

@app.route('/refresh_feed/<int:camera_id>')
def refresh_feed(camera_id):
    return redirect(url_for('manage_cameras'))

if __name__ == '__main__':
    app.run(debug=True,host="0.0.0.0")
