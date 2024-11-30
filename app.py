import requests
import os
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
import sqlite3
import logging
import re
from config import user_id, client_id, limit, offset
from flask import Flask, render_template, request, jsonify, send_from_directory, app
from retry import retry_with_logging

# Get the absolute path to the app's root directory
app_root = os.path.dirname(os.path.abspath(__file__))

# Define the path for your SQLite database relative to the app root
db_path = os.path.join(app_root, 'soundcloud.sqlite')

# Loading of static files (CSS/JS etc.)
app = Flask(__name__, static_folder='templates/static')

# Create tmp directory if it doesn't exist
os.makedirs('tmp', exist_ok=True)

conn = sqlite3.connect('soundcloud.sqlite', check_same_thread=False)
cursor = conn.cursor()

logging.basicConfig(level=logging.INFO)

# Because artists I listen to use silly shit in their titles..
def sanitize_filename(filename):
    # Replace invalid characters with underscores
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

# Create the likes table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS likes (
    user_id INT,
    client_id VARCHAR,
    track_id INT,
    m3u_url VARCHAR,
    title VARCHAR,
    album VARCHAR,
    artist VARCHAR,
    track_auth VARCHAR,
    artwork_url VARCHAR,
    stream_url VARCHAR,
    status TEXT DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'error'
    stage TEXT DEFAULT 'start',      -- 'start', 'stream_url_retrieved', 'm3u_url_retrieved', 'available_for_download', etc.
    file TEXT
)
''')
conn.commit()

def create_track_folder(track_id):
    """Creates a folder for each track."""
    track_folder = os.path.join('tmp', f"{track_id}")
    os.makedirs(track_folder, exist_ok=True)
    return track_folder

def get_liked_tracks(offset=None):
    """Retrieves liked tracks from SoundCloud."""
    url = f"https://api-v2.soundcloud.com/users/{user_id}/track_likes"
    params = {
        "client_id": client_id,
        "limit": limit,
        "offset": offset,
        "linked_partitioning": 1,
        "app_version": "1730449058",
        "app_locale": "en"
    }
    response = requests.get(url, params=params)

    if response.status_code == 200:
        return response.json().get('collection', [])
    else:
        print(f"Failed to retrieve liked tracks, status code: {response.status_code}")
        return []

def get_stream_url(track):
    """Gets the stream URL for a track."""
    transcodings = track.get('media', {}).get('transcodings', [])
    if transcodings:
        return transcodings[0].get('url')
    return None

def get_m3u_url(stream_url, track_id):
    """Fetches the m3u file URL."""
    stream_params = {
        "client_id": client_id,
        "track_authorization": stream_url  # Assuming 'stream_url' is actually the track_authorization
    }
    stream_response = requests.get(stream_url, params=stream_params)
    
    if stream_response.status_code == 200:
        return stream_response.json().get('url')
    else: 
            insert_or_update_track_info(user_id, client_id, track_id, status="error", stage="failed_retrieving_m3u")
    return None

def download_m3u_file(m3u_url, track_folder, track_id):
    """Downloads the m3u file and saves it in the track folder."""
    m3u_response = requests.get(m3u_url)
    if m3u_response.status_code == 200:
        m3u_file_path = os.path.join(track_folder, f"{track_id}.m3u")
        with open(m3u_file_path, 'wb') as m3u_file:
            m3u_file.write(m3u_response.content)
        print(f"Downloaded m3u file: {m3u_file_path}")
        return m3u_file_path
    print(f"Failed to download m3u file, status code: {m3u_response.status_code}")
    return None

def download_mp3_files(m3u_file_path, track_folder, track_id):
    """Downloads MP3 files listed in the m3u file."""
    if m3u_file_path:
        with open(m3u_file_path, 'r') as m3u_file:
            part_number = 1
            for line in m3u_file:
                url = line.strip()
                if url and not url.startswith('#'):
                    print(f"Downloading parts from URL: {url}")
                    response = requests.get(url)
                    if response.status_code == 200:
                        filename = os.path.join(track_folder, f"{track_id}-part{part_number}.mp3")
                        with open(filename, 'wb') as track_file:
                            track_file.write(response.content)
                        print(f"Downloaded file part: {filename}")
                        part_number += 1
                    else:
                        print(f"Failed to download file from {url}, status code: {response.status_code}")

def get_track_by_id(track_id):
    """
    Fetch a specific track by ID.
    :param track_id: The ID of the track to fetch.
    :return: A dictionary representing the track details.
    """
    get_stream_url(track_id)

from pydub.exceptions import CouldntDecodeError

def merge_audio_parts(track_id, track_folder, artist, title, user_id):
    """Merges audio parts into a single file (MP3 or AAC) and updates the database with the file location."""
    parts = []
    part_number = 1

    # Try MP3 format first
    while True:
        mp3_filename = os.path.join(track_folder, f"{track_id}-part{part_number}.mp3")
        aac_filename = os.path.join(track_folder, f"{track_id}-part{part_number}.aac")  # Checking for AAC format

        if os.path.exists(mp3_filename):
            try:
                audio_segment = AudioSegment.from_mp3(mp3_filename)
                audio_segment = audio_segment.set_frame_rate(44100).set_channels(2)  # Ensure consistent properties
                parts.append(audio_segment)
            except CouldntDecodeError as e:
                print(f"Error decoding {mp3_filename}: {e}")
                break  # Exit if MP3 format fails, proceed to AAC check
        elif os.path.exists(aac_filename):  # If MP3 fails, try AAC
            try:
                audio_segment = AudioSegment.from_file(aac_filename, format="aac")
                audio_segment = audio_segment.set_frame_rate(44100).set_channels(2)  # Ensure consistent properties
                parts.append(audio_segment)
            except CouldntDecodeError as e:
                print(f"Error decoding {aac_filename}: {e}")
            part_number += 1
        else:
            break

    if parts:
        # Start with the first part
        combined = parts[0]

        # Merge the parts directly
        for part in parts[1:]:
            combined = combined.append(part, crossfade=50)

        # Sanitize the filename to avoid invalid characters
        sanitized_title = sanitize_filename(f"{artist} - {title}.mp3")
        
        # Move the merged file to the tracks directory and create user folder if not exists
        tracks_dir = os.path.join("tracks", str(user_id))
        os.makedirs(tracks_dir, exist_ok=True)
        output_filename = os.path.join(tracks_dir, sanitized_title)

        # Export the combined file as MP3 first (default), fallback to AAC if needed
        try:
            combined.export(output_filename, format='mp3', bitrate="192k")
        except Exception as e:
            # Mark the track as merging failed in the database
            insert_or_update_track_info(user_id, track_id, status="error", stage="merging_mp3_failed")
            print(f"Failed to export MP3. Trying AAC format... {e}")
            insert_or_update_track_info(user_id, track_id, status="in_progress", stage="merging_aac_files")
            output_filename = os.path.splitext(output_filename)[0] + ".aac"  # Change extension to .aac
            combined.export(output_filename, format="aac", bitrate="192k")

        # Check if the output file was created successfully
        if os.path.exists(output_filename):
            print(f"Merged audio parts into: {output_filename}")
            
            # Update the database with the file location
            update_database_with_file_location(track_id, output_filename, user_id)

            return output_filename  # Return the file location to the front-end for playback
        else:
            print(f"Failed to create the final output file: {output_filename}")
            
            # Mark the track as merging failed in the database
            insert_or_update_track_info(user_id, track_id, status="error", stage="merging_failed")
            
    else:
        print(f"No parts found to merge for track ID: {track_id}")
         # Mark the track as downloading MP3 parts
        insert_or_update_track_info(user_id, track_id, status="error", stage="merging_mp3_failed")
        return None


def update_database_with_file_location(track_id, file_location, user_id):
    """Updates the track's record in the database with the file location."""
    try:
        conn = sqlite3.connect("soundcloud.sqlite")  # Replace with your actual database file
        cursor = conn.cursor()
        
        # Ensure the file location starts with 'tracks/' and replaces backslashes
        corrected_file_location = file_location.replace("\\", "/")
        if not corrected_file_location.startswith('tracks/'):
            corrected_file_location = f'tracks/{corrected_file_location}'

        # Update the track record with the corrected file location
        query = """
            UPDATE likes
            SET file_location = ?
            WHERE track_id = ? AND user_id = ?
        """
        cursor.execute(query, (corrected_file_location, track_id, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Database updated for track ID {track_id} with file location {corrected_file_location}")
    
    except sqlite3.Error as e:
        print(f"Error updating database: {e}")


def insert_or_update_track_info(user_id, client_id, track_id, **kwargs):
    """Updates track info and handles retries."""
    cursor.execute(
        '''SELECT m3u_url, stream_url, status, stage FROM likes WHERE user_id = ? AND client_id = ? AND track_id = ?''',
        (user_id, client_id, track_id)
    )
    existing_record = cursor.fetchone()

    if existing_record:
        # Update the existing record
        set_clause = ', '.join(f"{key} = ?" for key in kwargs.keys())
        values = list(kwargs.values()) + [user_id, client_id, track_id]
        query = f"UPDATE likes SET {set_clause} WHERE user_id = ? AND client_id = ? AND track_id = ?"
        cursor.execute(query, values)
        logging.info(f"Updated record for Track ID {track_id}: {kwargs}.")
    else:
        # Insert a new record
        query = '''
        INSERT INTO likes (user_id, client_id, track_id, m3u_url, title, album, artist, track_auth, stream_url, artwork_url, status, stage)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        values = (
            user_id, client_id, track_id,
            kwargs.get('m3u_url'),
            kwargs.get('title'),
            kwargs.get('album'),
            kwargs.get('artist'),
            kwargs.get('track_auth'),
            kwargs.get('stream_url'),
            kwargs.get('artwork_url'),
            kwargs.get('status', 'pending'),
            kwargs.get('stage', 'start')
        )
        cursor.execute(query, values)
        print(f"[INFO] Inserted new record for Track ID {track_id}: {kwargs}.")

    conn.commit()

def update_track_info(track_id, **kwargs):
    """Updates track information in the database."""
    set_clause = ', '.join(f"{key} = ?" for key in kwargs.keys())
    values = list(kwargs.values()) + [track_id]

    cursor.execute(f"UPDATE likes SET {set_clause} WHERE track_id = ?", values)
    print(f"[INFO] Updated Track ID {track_id} with {kwargs}.")
    conn.commit()
    

def process_tracks(track_id=None):
    """
    Process liked tracks. If a specific track_id is provided, process that track.
    Otherwise, process all liked tracks.

    :param track_id: ID of the track to process (optional).
    """
    if track_id:
        logging.info(f"Processing single track with ID: {track_id}")
        liked_tracks = [get_track_by_id(track_id)]  # Fetch single track details by ID
    else:
        logging.info("Processing all liked tracks.")
        liked_tracks = get_liked_tracks()  # Fetch all liked tracks

    # First, iterate over all liked tracks and store the stream URLs
    for item in liked_tracks:
        track = item.get('track', {})
        track_id = track.get('id')
        title = track.get('title')
        album_title = track.get('album', {}).get('title', '')
        artist = track.get('user', {}).get('username', '')
        artwork_url = track.get('artwork_url')
        track_authorization = track.get('track_authorization')

        # Check if the track is already completed
        cursor.execute(
            "SELECT status FROM likes WHERE user_id = ? AND client_id = ? AND track_id = ?",
            (user_id, client_id, track_id)
        )
        result = cursor.fetchone()
        if result and result[0] == "completed":
            logging.info(f"Skipping track ID {track_id}: already marked as 'completed'.")
            continue

        # Retry to get the stream URL
        stream_url = retry_with_logging(get_stream_url, max_retries=3, delay=2, track=track)
        if not stream_url:
            logging.info(f"Skipping track ID {track_id} due to failure in retrieving stream URL.")
            continue

        # Store stream URL and mark as in progress (for future steps)
        track_folder = create_track_folder(track_id)
        insert_or_update_track_info(
            user_id, client_id, track_id,
            title=title,
            album=album_title,
            track_auth=track_authorization,
            artist=artist,
            artwork_url=artwork_url,
            stream_url=stream_url,
            status="in_progress",
            stage="stream_url_retrieved"
        )
    
    # After stream URLs are collected, iterate again to process tracks one by one
    for item in liked_tracks:
        track = item.get('track', {})
        track_id = track.get('id')
        title = track.get('title')
        album_title = track.get('album', {}).get('title', '')
        artist = track.get('user', {}).get('username', '')
        artwork_url = track.get('artwork_url')
        track_authorization = track.get('track_authorization')

        # Retry to get the m3u URL
        cursor.execute(
            "SELECT status FROM likes WHERE user_id = ? AND client_id = ? AND track_id = ?",
            (user_id, client_id, track_id)
        )
        result = cursor.fetchone()
        if result and result[0] == "completed":
            logging.info(f"Skipping track ID {track_id}: already marked as 'completed'.")
            continue

        stream_url = retry_with_logging(get_stream_url, max_retries=3, delay=2, track=track)
        if not stream_url:
            logging.info(f"Skipping track ID {track_id} due to failure in retrieving stream URL.")
            continue
        
        # Retry to get the m3u URL
        m3u_url = retry_with_logging(get_m3u_url, max_retries=3, delay=2, stream_url=stream_url, track_id=track_id)
        if not m3u_url:
            logging.info(f"Skipping track ID {track_id} due to failure in retrieving m3u URL.")
            continue

        insert_or_update_track_info(
            user_id, client_id, track_id,
            m3u_url=m3u_url,
            album=album_title,
            artist=artist,
            stream_url=stream_url,
            status="in_progress",
            stage="m3u_url_retrieved"
        )

        # Download m3u file
        track_folder = create_track_folder(track_id)
        m3u_file_path = download_m3u_file(m3u_url, track_folder, track_id)  # Download m3u

        insert_or_update_track_info(
            user_id, client_id, track_id,
            status="in_progress",
            stage="downloading_mp3_parts"
        )

        # Download MP3 parts
        download_mp3_files(m3u_file_path, track_folder, track_id)  # Download MP3s 
        
        # Merge audio parts (optional, if needed)
        merge_audio_parts(track_id, track_folder, artist, title, user_id)

        # Mark track as completed
        insert_or_update_track_info(
            user_id, client_id, track_id,
            status="completed",
            stage="available_for_download"
        )

def delete_all_tracks():
    query = "DELETE FROM likes WHERE user_id > 1"
    cursor.execute(query)
    conn.commit()  
    print(f"deleted all tracks")


def get_tracks_from_db():
    """Retrieve relevant track details from the database."""
    # Connect to the SQLite database (adjust path if necessary)
    conn = sqlite3.connect('soundcloud.sqlite')
    cursor = conn.cursor()

    query = """
    SELECT title, artist, status, stage, artwork_url, file_location FROM likes;
    """
    cursor.execute(query)
    tracks = cursor.fetchall()

    # Close the database connection
    conn.close()

    # Return the tracks
    return tracks


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_tracks', methods=['GET'])
def get_tracks():
    tracks = get_tracks_from_db()
    # Convert the tracks into a list of dictionaries
    track_list = []
    for track in tracks:
        track_list.append({
            "title": track[0],
            "artist": track[1],
            "status": track[2],
            "stage": track[3],
            "artwork_url": track[4],
            "file_location": track[5]
        })
    
    response = jsonify(track_list)
    response.headers["Content-Type"] = "application/json"
    return response

@app.route('/load_liked_tracks', methods=['GET'])
def load_liked_tracks():
    try:
        process_tracks()  # Call the function to process tracks
        return jsonify({"message": "Tracks processing triggered successfully."}), 200
    except Exception as e:
        # Log the error for debugging
        logging.error(f"Error in load_liked_tracks: {e}")
        return jsonify({"error": "An error occurred while processing tracks.", "details": str(e)}), 500

# Serve files from the 'tracks' directory
@app.route('/tracks/<path:filename>')
def serve_track(filename):
    tracks_directory = os.path.join(app.root_path, 'tracks')  # Path to 'tracks' directory
    return send_from_directory(tracks_directory, filename)

if __name__ == '__main__':
    app.run(debug=True)


