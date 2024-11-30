# Why I started this project?

I live in Australia, where mobile internet is garbage. Going for night drives in remote areas can often result in internet data being unavailable, resulting in my soundcloud playlist being inaccessible. I have set out to remedy this problem as part of this little project.

Disclaimer: Soundcloud will not process my official API app request to do things "right". "Due to the high amount of requests recently received, we will no longer be processing API application requests at this time. We are working to re-evaluate our process to make it more efficient."

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
- [/] **UI**: Build a user interface to display the status of the processing tracks.
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

2. Retrieve your client_Id and user_id from soundcloud.com

- Visit soundcloud.com
- Hit F12 on your keyboard
- Click the *Network* tab
- Filter for /users
- Look for responses which contain "/users/{user_id}" and client_id={client_id}
- Add both these values to your config.py file

3. Create a `config.py` file with the following variables:

    ```python
    user_id = 'YOUR_USER_ID'
    client_id = 'YOUR_CLIENT_ID'
    limit = 200  # Number of tracks to fetch per request
    offset = 0  # Starting point for fetching tracks
    ```

4. Run the script:

    ```bash
    python app.py
    ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
