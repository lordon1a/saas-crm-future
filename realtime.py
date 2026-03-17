from flask_socketio import SocketIO


# Shared SocketIO instance initialized from app.py.
socketio = SocketIO()


def _build_message_payload(message, conversation, customer):
	sender_name = None
	avatar = None
	if message.sender_type == 'agent' and getattr(message, 'sender', None):
		sender_name = message.sender.name
		avatar = (sender_name[:1] or 'A').upper()
	else:
		sender_name = (customer.profile_name if customer else None) or 'Müşteri'
		avatar = (sender_name[:1] or 'M').upper()

	return {
		'id': message.id,
		'message_id': message.id,
		'conversation_id': conversation.id,
		'contact_id': conversation.customer_id,
		'customer_id': conversation.customer_id,
		'text': message.message_body,
		'message_body': message.message_body,
		'timestamp': message.created_at.isoformat() if message.created_at else None,
		'created_at': message.created_at.isoformat() if message.created_at else None,
		'channel': getattr(message, 'channel', 'whatsapp') or 'whatsapp',
		'sender_type': message.sender_type,
		'message_side': 'outbound' if message.sender_type == 'agent' else 'inbound',
		'sender_name': sender_name,
		'avatar': avatar,
		'media_type': getattr(message, 'media_type', None),
		'media_url': f"/api/media/{message.media_url}" if getattr(message, 'media_url', None) else None,
	}


def emit_chat_message_event(message_id, workspace_id=None):
	# Local import avoids circular dependencies during app bootstrap.
	from models import Message, Conversation, Customer

	message = Message.query.get(message_id)
	if not message:
		return False

	conversation = Conversation.query.get(message.conversation_id)
	if not conversation:
		return False

	customer = Customer.query.get(conversation.customer_id) if conversation.customer_id else None
	resolved_workspace_id = workspace_id or conversation.workspace_id
	payload = _build_message_payload(message, conversation, customer)

	socketio.emit('new_message', payload, room=f'contact_{conversation.customer_id}')
	socketio.emit('new_incoming_message', payload, room=f'contact_{conversation.customer_id}')
	socketio.emit(
		'inbox_updated',
		{
			'conversation_id': conversation.id,
			'contact_id': conversation.customer_id,
			'message_id': message.id,
			'message_side': payload['message_side'],
			'channel': payload['channel'],
		},
		room=f'ws_{resolved_workspace_id}',
	)
	return True
