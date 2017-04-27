# Debug mode during development
# WARNING: DISABLE BEFORE DEPLOYMENT
DEBUG = True

# Define the application directory
import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Database
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
DATABASE_CONNECT_OPTIONS = {}

#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

# Application threads. A common general assumption is
# using 2 per available processor cores - to handle
# incoming requests using one and performing background
# operations using the other.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)*
CSRF_ENABLED     = True

# Use a secure, unique and absolutely secret key for
# signing the data. 
CSRF_SESSION_KEY = "SECRET_CHANGE_THIS_T5c1N1YYmDgA_2wF+dTP1Fs7U_YEDX0"

# Secret key for signing cookies
SECRET_KEY = "SECRET_CHANGE_THIS_afsj8dulckv78++*_HDGHCHSDF54g..nbv"

#
BASE_URL = ""

# Bitmon task config
#####################
BITCOIN_CONF = {
    # URL for bitcoind node JSON-RPC service
    'BITCOIND_URL': 'http://secnot:12345@127.0.0.1:8332',
    
    # Number of confirmations required to accept a transaction.
    'CONFIRMATIONS': 3,

    # Bitcoin chain used 'testnet' or 'mainnet'
    'CHAIN': 'testnet'}

# Callback task config
#######################
CALLBACK_CONF = {
    # Max number of retries before acknowledgment
    'RETRIES': 3,

    # Time between retries (in seconds)
    'RETRY_PERIOD': 120,

    # Timeout for unresponsive callbacks (seconds)
    'TIMEOUT': 3, 

    # Callback threads 
    'THREADS': 4,

    # Callback signing key
    'SIGNKEY_PATH': os.path.join(BASE_DIR, 'private.pem'),

    # Default callback POST url
    'POST_URL': "http://localhost:8080"}
