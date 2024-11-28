
# SoundCloud Bulk Track Processor

This script retrieves liked tracks from SoundCloud in bulk, handles retries for fetching track data, downloads MP3 parts, and merges them into a single file. It aims to address the lack of tooling for fetching multiple tracks at once by automating the download process.

## Features

- Fetch liked tracks from SoundCloud API.
- Retry fetching track data with logging.
- Create directories for each track.
- Download M3U files and MP3 files for tracks.
- Merge MP3 parts into a single file.
- Save information to an SQLite database.

## Steps in the Process

1. **Fetch Liked Tracks**: Retrieve liked tracks from SoundCloud using the API with pagination (using `limit` and `offset`).
2. **Get Stream URL**: Fetch the stream URL for each track.
3. **Get M3U URL**: Fetch the M3U URL from the stream URL.
4. **Download MP3 Parts**: Download MP3 file parts from the M3U file.
5. **Merge MP3 Parts**: Combine the MP3 parts into a single file.
6. **Update Database**: Insert or update track information into an SQLite database with status and file location.

## To-Do List

- [ ] **Retry fetching likes**: Implement retry logic for fetching tracks if the initial request fails.
- [ ] **UI**: Build a user interface to display the status of the processing tracks.
- [ ] **Fetch specific track**: Add functionality to fetch and process a specific track by its ID.
- [ ] **Error Handling**: Improve error handling for network and file I/O issues.
- [ ] **File Cleanup**: Implement cleanup of temporary files after processing.
- [ ] **Track Download Progress**: Add progress logging for the track download process.

## Requirements

- Python 3.x
- `requests` library
- `pydub` library
- SQLite3

## Setup

1. Install the necessary dependencies:

    ```bash
    pip install requests pydub
    ```

2. Create a `config.py` file with the following variables:

    ```python
    user_id = 'YOUR_USER_ID'
    client_id = 'YOUR_CLIENT_ID'
    limit = 200  # Number of tracks to fetch per request
    offset = 0  # Starting point for fetching tracks
    ```

3. Run the script:

    ```bash
    python app.py
    ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
