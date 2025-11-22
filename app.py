from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import ffmpeg
import requests
import os
import tempfile
import uuid
import logging
import subprocess

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/merge', methods=['POST'])
def merge_video_audio():
    try:
        data = request.json
        video_url = data.get('video_url')
        audio_url = data.get('audio_url')
        
        if not video_url or not audio_url:
            return jsonify({'error': 'Missing video_url or audio_url'}), 400
        
        logger.info(f"Video URL: {video_url}")
        logger.info(f"Audio URL: {audio_url}")
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        audio_path = os.path.join(temp_dir, 'audio.m4a')
        output_path = os.path.join(temp_dir, f'output_{uuid.uuid4()}.mp4')
        
        # Download video
        logger.info("Downloading video...")
        video_response = requests.get(video_url, stream=True, timeout=180)
        video_response.raise_for_status()
        with open(video_path, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Video downloaded: {os.path.getsize(video_path)} bytes")
        
        # Download audio
        logger.info("Downloading audio...")
        audio_response = requests.get(audio_url, stream=True, timeout=180)
        audio_response.raise_for_status()
        with open(audio_path, 'wb') as f:
            for chunk in audio_response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Audio downloaded: {os.path.getsize(audio_path)} bytes")
        
        # Get audio duration
        logger.info("Probing audio duration...")
        audio_probe = ffmpeg.probe(audio_path)
        audio_duration = float(audio_probe['format']['duration'])
        logger.info(f"Audio duration: {audio_duration}s")
        
        # Get video duration
        video_probe = ffmpeg.probe(video_path)
        video_duration = float(video_probe['format']['duration'])
        logger.info(f"Video duration: {video_duration}s")
        
        # Merge using direct FFmpeg command (more reliable than ffmpeg-python for complex operations)
        logger.info("Merging video and audio...")
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-stream_loop', '-1',  # Loop video
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:v', '2M',
            '-b:a', '192k',
            '-t', str(audio_duration),  # Match audio duration
            '-preset', 'ultrafast',
            '-movflags', 'faststart',
            '-y',  # Overwrite output
            output_path
        ]
        
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg stderr: {result.stderr}")
            return jsonify({
                'error': f'FFmpeg failed: {result.stderr}'
            }), 500
        
        logger.info(f"Merge complete: {output_path}")
        
        # Check output file
        if not os.path.exists(output_path):
            logger.error("Output file not created")
            return jsonify({'error': 'Output file not created'}), 500
            
        output_size = os.path.getsize(output_path)
        logger.info(f"Output file size: {output_size} bytes")
        
        if output_size == 0:
            logger.error("Output file is empty")
            return jsonify({'error': 'Output file is empty'}), 500
        
        # Return the merged file
        return send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f'merged_{uuid.uuid4()}.mp4'
        )
    
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout")
        return jsonify({'error': 'Processing timeout - video too large'}), 500
    except requests.exceptions.RequestException as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': f'Download error: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'video-merger', 'version': 'v4.0'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
