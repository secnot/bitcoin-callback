from flask import Flask
import os
from multiprocessing import Process, Queue
import ecdsa
import atexit

from bitcallback.commands import *
from bitcallback.bitmon_task import bitcoin_task
from bitcallback.callback_task import callback_task



QUEUE_SIZE = 4000


def create_app(name):
    """See http://stackoverflow.com/questions/14384739/how-can-i-add-a-background-thread-to-flask"""

    app = Flask(name)
    app.config.from_object('config')
    
    bitcoin_conf = app.config['BITCOIN_CONF']
    callback_conf = app.config['CALLBACK_CONF']

    # Initilize IPC queue for bitmon_task and callback_task
    bitmon_q = Queue(QUEUE_SIZE)

    # Output from bitcoin task, input to callback task
    callback_q = Queue(QUEUE_SIZE)

    # Load ecdsa request signing key
    with open(callback_conf['SIGNKEY_PATH'], 'r') as f:
        key = f.read()
    sign_key = ecdsa.SigningKey.from_pem(key)

    # Initialize and start bitcoin and callback processes
    bit_kwargs = {
        'input_q': bitmon_q, 
        'callback_q': callback_q,
        'settings': bitcoin_conf}
   

    call_kwargs = {
        'input_q': callback_q,
        'sign_key': sign_key,
        'settings': callback_conf}

    bit_task = Process(target=bitcoin_task, kwargs=bit_kwargs)
    call_task = Process(target=callback_task, kwargs=call_kwargs)
    
    bit_task.start()
    call_task.start()

    # When a kill (SIGTERM) signal is received notify other tasks
    def cleanUp():
        bitmon_q.put((EXIT_TASK, None))
        callback_q.put((EXIT_TASK, None))
        bitmon_q.close()
        callback_q.close()
        #bit_task.join()
        #call_task.join()
    
    #atexit.register(cleanUp)

    return app, bitmon_q, callback_q

