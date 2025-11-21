from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import ffmpeg
import requests
import os
import tempfile
import uuid

app = Flask(__name__)
CORS(app)

@app.route('/merge', methods=['POST'])
def merge_video_audio():
    try:
        data = request.json
        video_url = data.get('video_url')
        audio_url = data.get('audio_url')
        
        if not video_url or not audio_url:
            return jsonify({'error': 'Missing video_url or audio_url'}), 400
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        audio_path = os.path.join(temp_dir, 'audio.mp3')
        output_path = os.path.join(temp_dir, f'output_{uuid.uuid4()}.mp4')
        
        # Download video
        print(f"Downloading video from: {video_url}")
        video_response = requests.get(video_url, stream=True, timeout=120)
        video_response.raise_for_status()
        with open(video_path, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Download audio
        print(f"Downloading audio from: {audio_url}")
        audio_response = requests.get(audio_url, stream=True, timeout=120)
        audio_response.raise_for_status()
        with open(audio_path, 'wb') as f:
            for chunk in audio_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Merge using ffmpeg
        print("Merging video and audio...")
        video_stream = ffmpeg.input(video_path)
        audio_stream = ffmpeg.input(audio_path)
        
        ffmpeg.output(
            video_stream,
            audio_stream,
            output_path,
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='192k',
            shortest=None,
            **{'movflags': 'faststart'}
        ).overwrite_output().run(quiet=True, capture_stdout=True, capture_stderr=True)
        
        print(f"Merge complete: {output_path}")
        
        # Return the merged file
        return send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f'merged_{uuid.uuid4()}.mp4'
        )
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Download error: {str(e)}'}), 500
    except ffmpeg.Error as e:
        return jsonify({'error': f'FFmpeg error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'video-merger'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
