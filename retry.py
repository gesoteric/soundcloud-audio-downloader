import logging
import time

def retry_with_logging(func, max_retries=3, delay=2, *args, **kwargs):
    """
    Retry a function up to max_retries times with a delay between attempts.
    Logs retries and failures.

    :param func: Function to retry.
    :param max_retries: Number of retry attempts.
    :param delay: Delay between retries in seconds.
    :param args: Positional arguments for the function.
    :param kwargs: Keyword arguments for the function.
    :return: Result of the function if successful, or None if all retries fail.
    """
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Attempt {attempt}/{max_retries} for {func.__name__}.")
            result = func(*args, **kwargs)
            if result:
                return result
        except Exception as e:
            logging.warning(f"Attempt {attempt} failed for {func.__name__}: {e}")
        time.sleep(delay)
    logging.warning(f"All {max_retries} attempts failed for {func.__name__}.")
    return None

# Because artists I listen to use silly shit in their titles..
def sanitize_filename(filename):
    # Replace invalid characters with underscores
    return re.sub(r'[<>:"/\\|?*]', '_', filename)