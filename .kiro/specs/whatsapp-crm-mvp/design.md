# Tasarım Dokümanı: WhatsApp CRM MVP (Versiyon 1.0)

## Genel Bakış

WhatsApp CRM MVP, Flask tabanlı monolitik bir web uygulamasıdır. Meta WhatsApp Cloud API ile entegre çalışarak müşteri mesajlarını alır, PostgreSQL veritabanında saklar ve temsilcilerin HTML/CSS/JS tabanlı bir arayüzden yanıt vermesini sağlar. Sistem webhook tabanlı mesaj alımı ve REST API tabanlı mesaj gönderimi kullanır.

## Mimari

### Sistem Bileşenleri

```
┌─────────────────┐
│   WhatsApp      │
│   (Müşteri)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Meta WhatsApp Cloud API           │
│   - Webhook (Gelen Mesajlar)        │
│   - Messages API (Giden Mesajlar)   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Flask Backend                     │
│   - Webhook Handler (/webhook)      │
│   - REST API Endpoints              │
│   - SQLAlchemy ORM                  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   PostgreSQL Database               │
│   - users, customers                │
│   - conversations, messages         │
│   - quick_replies                   │
└─────────────────────────────────────┘
         ▲
         │
┌────────┴────────────────────────────┐
│   Frontend (HTML/CSS/JS)            │
│   - Konuşma Listesi                 │
│   - Mesaj Görüntüleme               │
│   - Mesaj Gönderme                  │
│   - Polling/Socket.io               │
└─────────────────────────────────────┘
```

### Teknoloji Yığını

- **Backend Framework**: Flask 3.0+
- **ORM**: SQLAlchemy 2.0+
- **Database**: PostgreSQL 15+
- **Frontend**: Vanilla JavaScript + TailwindCSS 3.0+
- **Real-time**: JavaScript Polling (5 saniye interval) veya Socket.io
- **HTTP Client**: requests library (Meta API çağrıları için)
- **Authentication**: Flask-Login (session-based)
- **Password Hashing**: werkzeug.security (pbkdf2:sha256)

## Bileşenler ve Arayüzler

### 1. Webhook Handler Modülü

**Sorumluluk**: Meta'dan gelen webhook isteklerini işlemek

**Arayüz**:
```python
class WebhookHandler:
    def verify_webhook(verify_token: str, challenge: str) -> tuple[str, int]:
        """
        Meta webhook doğrulaması yapar
        Args:
            verify_token: Meta'dan gelen token
            challenge: Geri dönülecek challenge değeri
        Returns:
            (challenge, 200) veya (error_message, 403)
        """
        pass
    
    def process_incoming_message(payload: dict) -> dict:
        """
        Gelen mesajı işler ve veritabanına kaydeder
        Args:
            payload: Meta'dan gelen JSON payload
        Returns:
            {"status": "success", "message_id": int} veya error dict
        """
        pass
    
    def extract_message_data(payload: dict) -> dict:
        """
        Meta payload'ından mesaj bilgilerini çıkarır
        Args:
            payload: Meta JSON payload
        Returns:
            {
                "phone_number": str,
                "profile_name": str,
                "message_body": str,
                "meta_message_id": str,
                "timestamp": int
            }
        """
        pass
```

**İşlem Akışı**:
1. POST /webhook isteği gelir
2. Payload'dan mesaj bilgileri extract edilir
3. Müşteri kaydı kontrol edilir/oluşturulur
4. Açık conversation kontrol edilir/oluşturulur
5. Mesaj messages tablosuna kaydedilir
6. Frontend'e bildirim gönderilir

### 2. Customer Manager Modülü

**Sorumluluk**: Müşteri kayıtlarını yönetmek

**Arayüz**:
```python
class CustomerManager:
    def get_or_create_customer(phone_number: str, profile_name: str) -> Customer:
        """
        Müşteriyi bulur veya oluşturur
        Args:
            phone_number: WhatsApp telefon numarası (WA_ID)
            profile_name: Meta'dan gelen profil adı
        Returns:
            Customer object
        """
        pass
    
    def get_customer_by_phone(phone_number: str) -> Optional[Customer]:
        """
        Telefon numarasına göre müşteri bulur
        """
        pass
    
    def update_customer_profile(customer_id: int, profile_name: str) -> Customer:
        """
        Müşteri profil adını günceller
        """
        pass
```

### 3. Conversation Manager Modülü

**Sorumluluk**: Konuşma oturumlarını yönetmek

**Arayüz**:
```python
class ConversationManager:
    def get_or_create_conversation(customer_id: int) -> Conversation:
        """
        Müşterinin açık conversation'ını bulur veya yeni oluşturur
        Args:
            customer_id: Müşteri ID
        Returns:
            Conversation object (status='open')
        """
        pass
    
    def get_conversations(status: Optional[str] = None, limit: int = 50) -> List[Conversation]:
        """
        Konuşmaları last_message_at'e göre sıralı getirir
        Args:
            status: Filtrelemek için status ('open', 'resolved', 'pending')
            limit: Maksimum kayıt sayısı
        Returns:
            Conversation listesi (customer bilgileri ile birlikte)
        """
        pass
    
    def update_conversation_tag(conversation_id: int, tag: str) -> Conversation:
        """
        Conversation etiketini günceller
        """
        pass
    
    def update_last_message_time(conversation_id: int, timestamp: datetime) -> None:
        """
        Conversation'ın last_message_at değerini günceller
        """
        pass
    
    def close_conversation(conversation_id: int) -> Conversation:
        """
        Conversation'ı kapatır (status='resolved')
        """
        pass
```

### 4. Message Manager Modülü

**Sorumluluk**: Mesaj kayıtlarını yönetmek

**Arayüz**:
```python
class MessageManager:
    def save_incoming_message(
        conversation_id: int,
        message_body: str,
        meta_message_id: str
    ) -> Message:
        """
        Gelen mesajı kaydeder
        Args:
            conversation_id: Konuşma ID
            message_body: Mesaj içeriği
            meta_message_id: Meta'dan gelen message ID
        Returns:
            Message object (sender_type='customer')
        """
        pass
    
    def save_outgoing_message(
        conversation_id: int,
        message_body: str,
        sender_id: int,
        meta_message_id: str
    ) -> Message:
        """
        Giden mesajı kaydeder
        Args:
            conversation_id: Konuşma ID
            message_body: Mesaj içeriği
            sender_id: Gönderen agent ID
            meta_message_id: Meta'dan dönen message ID
        Returns:
            Message object (sender_type='agent')
        """
        pass
    
    def get_conversation_messages(conversation_id: int) -> List[Message]:
        """
        Bir konuşmanın tüm mesajlarını created_at'e göre sıralı getirir
        Args:
            conversation_id: Konuşma ID
        Returns:
            Message listesi (sender bilgileri ile birlikte)
        """
        pass
```

### 5. Meta API Client Modülü

**Sorumluluk**: Meta WhatsApp Cloud API ile iletişim

**Arayüz**:
```python
class MetaAPIClient:
    def __init__(self, access_token: str, phone_number_id: str):
        """
        Args:
            access_token: Meta API Bearer Token
            phone_number_id: WhatsApp Business Phone Number ID
        """
        pass
    
    def send_text_message(to: str, message: str) -> dict:
        """
        WhatsApp üzerinden text mesajı gönderir
        Args:
            to: Alıcı telefon numarası
            message: Mesaj içeriği
        Returns:
            {
                "success": bool,
                "message_id": str,
                "error": Optional[str]
            }
        """
        pass
    
    def mark_message_as_read(message_id: str) -> dict:
        """
        Mesajı okundu olarak işaretler
        """
        pass
```

**Meta API Endpoint**:
- Base URL: `https://graph.facebook.com/v18.0`
- Send Message: `POST /{phone_number_id}/messages`
- Headers: `Authorization: Bearer {access_token}`

**Request Format**:
```json
{
  "messaging_product": "whatsapp",
  "to": "905551234567",
  "type": "text",
  "text": {
    "body": "Mesaj içeriği"
  }
}
```

### 6. Quick Reply Manager Modülü

**Sorumluluk**: Hazır yanıt şablonlarını yönetmek

**Arayüz**:
```python
class QuickReplyManager:
    def get_all_quick_replies() -> List[QuickReply]:
        """
        Tüm hazır yanıtları getirir
        """
        pass
    
    def create_quick_reply(title: str, body: str) -> QuickReply:
        """
        Yeni hazır yanıt oluşturur
        """
        pass
    
    def get_quick_reply_by_id(reply_id: int) -> Optional[QuickReply]:
        """
        ID'ye göre hazır yanıt getirir
        """
        pass
```

### 7. Authentication Manager Modülü

**Sorumluluk**: Kullanıcı kimlik doğrulama ve oturum yönetimi

**Arayüz**:
```python
class AuthManager:
    def authenticate_user(email: str, password: str) -> Optional[User]:
        """
        Kullanıcı girişi yapar
        Args:
            email: Kullanıcı email
            password: Plain text şifre
        Returns:
            User object veya None
        """
        pass
    
    def hash_password(password: str) -> str:
        """
        Şifreyi hash'ler
        """
        pass
    
    def verify_password(password_hash: str, password: str) -> bool:
        """
        Şifre doğrulaması yapar
        """
        pass
    
    def create_user(name: str, email: str, password: str, role: str) -> User:
        """
        Yeni kullanıcı oluşturur
        """
        pass
```

## Veri Modelleri

### Database Schema (SQLAlchemy Models)

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # 'admin' or 'agent'
    
    # Relationships
    messages = relationship('Message', back_populates='sender')

class Customer(Base):
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    profile_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    conversations = relationship('Conversation', back_populates='customer')

class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False, index=True)
    status = Column(String(20), default='open', nullable=False, index=True)
    tag = Column(String(50))
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    customer = relationship('Customer', back_populates='conversations')
    messages = relationship('Message', back_populates='conversation', order_by='Message.created_at')

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False, index=True)
    sender_type = Column(String(20), nullable=False)  # 'customer' or 'agent'
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    message_body = Column(Text, nullable=False)
    meta_message_id = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    conversation = relationship('Conversation', back_populates='messages')
    sender = relationship('User', back_populates='messages')

class QuickReply(Base):
    __tablename__ = 'quick_replies'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
```

### Database Indexes

Performans için gerekli indexler:
- `customers.phone_number` (unique index)
- `users.email` (unique index)
- `conversations.customer_id` (foreign key index)
- `conversations.status` (filter için)
- `conversations.last_message_at` (sorting için)
- `messages.conversation_id` (foreign key index)
- `messages.meta_message_id` (unique index)
- `messages.created_at` (sorting için)

## API Endpoints

### Webhook Endpoints

#### GET /webhook
**Amaç**: Meta webhook doğrulaması

**Query Parameters**:
- `hub.mode`: "subscribe"
- `hub.verify_token`: Doğrulama token'ı
- `hub.challenge`: Geri dönülecek değer

**Response**:
- Success: `200 OK` + challenge değeri (plain text)
- Failure: `403 Forbidden`

#### POST /webhook
**Amaç**: Gelen mesajları almak

**Request Body** (Meta'dan gelen):
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "phone_number_id": "123456789"
        },
        "contacts": [{
          "profile": {
            "name": "Ahmet Yılmaz"
          },
          "wa_id": "905551234567"
        }],
        "messages": [{
          "from": "905551234567",
          "id": "wamid.XXX",
          "timestamp": "1234567890",
          "type": "text",
          "text": {
            "body": "Merhaba, sipariş durumu nedir?"
          }
        }]
      }
    }]
  }]
}
```

**Response**:
- `200 OK` (Meta her zaman 200 bekler)

### Internal API Endpoints

#### GET /api/conversations
**Amaç**: Konuşma listesini getirmek

**Query Parameters**:
- `status` (optional): 'open', 'resolved', 'pending'
- `limit` (optional): default 50

**Response**:
```json
{
  "conversations": [
    {
      "id": 1,
      "customer": {
        "id": 1,
        "phone_number": "905551234567",
        "profile_name": "Ahmet Yılmaz"
      },
      "status": "open",
      "tag": "yeni_siparis",
      "last_message_at": "2024-01-15T10:30:00Z",
      "unread_count": 2
    }
  ]
}
```

#### GET /api/conversations/<id>/messages
**Amaç**: Bir konuşmanın mesaj geçmişini getirmek

**Response**:
```json
{
  "messages": [
    {
      "id": 1,
      "sender_type": "customer",
      "message_body": "Merhaba",
      "created_at": "2024-01-15T10:00:00Z"
    },
    {
      "id": 2,
      "sender_type": "agent",
      "sender_name": "Ayşe Demir",
      "message_body": "Merhaba, nasıl yardımcı olabilirim?",
      "created_at": "2024-01-15T10:01:00Z"
    }
  ]
}
```

#### POST /api/messages/send
**Amaç**: Müşteriye mesaj göndermek

**Request Body**:
```json
{
  "conversation_id": 1,
  "message": "Siparişiniz kargoya verildi."
}
```

**Response**:
```json
{
  "success": true,
  "message_id": 123,
  "meta_message_id": "wamid.YYY"
}
```

**Error Response**:
```json
{
  "success": false,
  "error": "Meta API error: Invalid phone number"
}
```

#### PUT /api/conversations/<id>/tag
**Amaç**: Konuşma etiketini güncellemek

**Request Body**:
```json
{
  "tag": "kargo_sorunu"
}
```

**Response**:
```json
{
  "success": true,
  "conversation": {
    "id": 1,
    "tag": "kargo_sorunu"
  }
}
```

#### GET /api/quick-replies
**Amaç**: Hazır yanıt listesini getirmek

**Response**:
```json
{
  "quick_replies": [
    {
      "id": 1,
      "title": "IBAN Bilgisi",
      "body": "IBAN: TR55 0000 0000 0000 0000 0000 00"
    }
  ]
}
```

## Doğruluk Özellikleri (Correctness Properties)

*Bir özellik (property), sistemin tüm geçerli çalıştırmalarında doğru olması gereken bir karakteristik veya davranıştır - esasen, sistemin ne yapması gerektiğine dair formal bir ifadedir. Özellikler, insan tarafından okunabilir spesifikasyonlar ile makine tarafından doğrulanabilir doğruluk garantileri arasında köprü görevi görür.*

