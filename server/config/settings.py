import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOST = "127.0.0.1"
PORT = 9999
MAX_LISTEN = 5

USER_HOME_DIR = os.path.join(BASE_DIR, "home")
ACCOUNT_FILE = os.path.join(BASE_DIR, "config", "account.ini")

MAX_CONCURRENT_AMOUNT = 2
