from flask_socketio import SocketIO


# Use gevent async mode to stay compatible with current deployment stack.
socketio = SocketIO(cors_allowed_origins='*', async_mode='gevent', manage_session=False)
